import { transformFile } from "@swc/core";

const files = JSON.parse(process.argv[2]);

async function run() {
  let output = "";

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const isLastFile = i === files.length - 1;
    const componentName = isLastFile ? "Page" : `Layout${i}`;

    const { code } = await transformFile(file, {
      jsc: {
        parser: { syntax: "typescript", tsx: true },
        transform: {
          react: {
            runtime: "automatic"
          }
        },
        target: "es2022"
      },
      module: { type: "es6" }
    });

    // Replace `export default` with a named constant.
    const transformedCode = code.replace(
      /export default\s/,
      `const ${componentName} = `
    );
    output += transformedCode + "\n";
  }

  console.log(output);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
