use anyhow::Result;
use std::io;
use swc_core::{
    common::{
        errors::Handler,
        sync::Lrc,
        Mark, SourceMap, GLOBALS,
    },
    ecma::{
        ast::{EsVersion, Program},
        codegen::{
            text_writer::JsWriter,
            Config as CodegenConfig, Emitter,
        },
        parser::{lexer::Lexer, Parser, StringInput, Syntax, TsSyntax},
        transforms::{
            base::resolver,
            react::{react, Options as ReactOptions, Runtime},
            typescript::{strip, Config},
        },
        visit::{FoldWith, FoldPass},
    },
};
use swc_common::{FileName, FilePathMapping, SourceFile};
use crate::cli::Args;

pub struct TranspileOptions {
    pub minify: bool,
    pub sourcemap: bool,
    pub jsx: bool,
    pub typescript: bool,
}

pub fn transpile_code(code: &str, args: &Args) -> Result<String> {
    let options = TranspileOptions {
        minify: args.minify,
        sourcemap: args.sourcemap,
        jsx: true,
        typescript: true,
    };
    
    transpile_with_options(code, &options)
}

pub fn transpile_with_options(code: &str, options: &TranspileOptions) -> Result<String> {
    GLOBALS.set(&Default::default(), || {
        let cm = Lrc::new(SourceMap::new(FilePathMapping::empty()));
        let _handler = Handler::with_emitter_writer(Box::new(io::stderr()), Some(cm.clone()));

        let source_file = cm.new_source_file(
            Lrc::new(FileName::Custom("virtual_entry.tsx".into())),
            code.to_string(),
        );

        let result = transpile_inner(source_file, options, cm.clone());
        
        match result {
            Ok(output) => Ok(output),
            Err(e) => {
                eprintln!("SWC Error: {:#}", e);
                Err(e)
            }
        }
    })
}

fn transpile_inner(
    source_file: Lrc<SourceFile>,
    options: &TranspileOptions,
    cm: Lrc<SourceMap>,
) -> Result<String> {
    let unresolved_mark = Mark::fresh(Mark::root());
    let top_level_mark = Mark::fresh(Mark::root());

    let syntax = Syntax::Typescript(TsSyntax {
        tsx: options.jsx,
        decorators: false,
        dts: false,
        no_early_errors: false,
        disallow_ambiguous_jsx_like: false,
    });

    let lexer = Lexer::new(
        syntax,
        EsVersion::Es2020,
        StringInput::from(&*source_file),
        None,
    );

    let mut parser = Parser::new_from(lexer);
    let module = parser.parse_module()
        .map_err(|e| anyhow::anyhow!("Parse error: {:?}", e))?;

    let mut program = Program::Module(module);

    // Apply transformations
    program = program.fold_with(&mut resolver(unresolved_mark, top_level_mark, false));
    program = program.fold_with(&mut strip(Config::default(), unresolved_mark, top_level_mark));
    program = program.fold_with(&mut react(
        cm.clone(),
        None,
        ReactOptions {
            development: Some(false),
            refresh: Default::default(),
            import_source: Default::default(),
            pragma: Default::default(),
            pragma_frag: Default::default(),
            throw_if_namespace: Default::default(),
            runtime: Some(Runtime::Classic),
            next: Default::default(),
            use_builtins: None,
            use_spread: None,
        },
        unresolved_mark,
        top_level_mark,
    ));

    let module = match program {
        Program::Module(m) => m,
        _ => unreachable!(),
    };

    // Generate code
    let mut buf = Vec::new();
    let sourcemap_buf = if options.sourcemap { Some(Vec::new()) } else { None };
    
    let writer = match sourcemap_buf {
        Some(mut sm_buf) => JsWriter::new(cm.clone(), "\n", &mut buf, Some(&mut sm_buf)),
        None => JsWriter::new(cm.clone(), "\n", &mut buf, None),
    };

    let mut emitter = Emitter {
        cfg: CodegenConfig::default().with_minify(options.minify),
        cm: cm.clone(),
        comments: None,
        wr: writer,
    };

    emitter.emit_module(&module)
        .map_err(|e| anyhow::anyhow!("Codegen error: {:?}", e))?;

    let transpiled_code = String::from_utf8(buf)
        .map_err(|e| anyhow::anyhow!("UTF-8 conversion error: {}", e))?;

    Ok(transpiled_code)
}