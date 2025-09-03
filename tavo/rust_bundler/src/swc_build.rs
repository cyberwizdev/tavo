use anyhow::Result;
use swc_core::{
    common::{
        errors::{ColorConfig, Handler},
        sync::Lrc,
        SourceMap, GLOBALS,
    },
    ecma::{
        ast::*,
        codegen::{
            text_writer::JsWriter,
            Config as CodegenConfig, Emitter,
        },
        parser::{lexer::Lexer, Parser, StringInput, Syntax, TsConfig},
        transforms::{
            base::{feature::FeatureFlag, resolver},
            react::{react, Options as ReactOptions},
            typescript::typescript,
        },
        visit::FoldWith,
    },
};
use swc_common::{BytePos, FileName, FilePathMapping, SourceFile};
use std::path::Path;
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
        let handler = Handler::with_tty_emitter(
            ColorConfig::Auto,
            true,
            false,
            Some(cm.clone()),
        );

        let source_file = cm.new_source_file(
            FileName::Custom("virtual_entry.tsx".into()),
            code.into(),
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
    let syntax = Syntax::Typescript(TsConfig {
        tsx: options.jsx,
        decorators: true,
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

    // Apply transformations
    let module = module
        .fold_with(&mut resolver(
            Default::default(),
            Default::default(),
            false,
        ))
        .fold_with(&mut typescript::typescript(
            Default::default(),
            Default::default(),
            cm.clone(),
        ))
        .fold_with(&mut react(
            cm.clone(),
            Some(&Default::default()),
            ReactOptions {
                development: false,
                refresh: Default::default(),
                import_source: Default::default(),
                pragma: Default::default(),
                pragma_frag: Default::default(),
                throw_if_namespace: Default::default(),
                runtime: Default::default(),
                use_built_ins: Default::default(),
                use_spread: Default::default(),
                next: Default::default(),
            },
            Default::default(),
            FeatureFlag::all(),
        ));

    // Generate code
    let mut buf = Vec::new();
    let mut emitter = Emitter {
        cfg: CodegenConfig::default().with_minify(options.minify),
        cm: cm.clone(),
        comments: None,
        wr: JsWriter::new(cm, "\n", &mut buf, None),
    };

    emitter.emit_module(&module)
        .map_err(|e| anyhow::anyhow!("Codegen error: {:?}", e))?;

    let transpiled_code = String::from_utf8(buf)
        .map_err(|e| anyhow::anyhow!("UTF-8 conversion error: {}", e))?;

    Ok(transpiled_code)
}