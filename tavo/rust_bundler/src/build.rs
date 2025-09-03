use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use fs_extra::dir::{copy as copy_dir, CopyOptions};

fn main() {
    // Get the project root
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let project_root = Path::new(&manifest_dir);

    // Define source paths in node_modules
    let node_modules = project_root.join("node_modules");
    let react_umd = node_modules.join("react/umd");
    let react_dom_umd = node_modules.join("react-dom/umd");

    // Target vendor directory
    let out_dir = project_root.join("vendor");

    // Create vendor directory if it doesn't exist
    if !out_dir.exists() {
        fs::create_dir_all(&out_dir).expect("Failed to create vendor directory");
    }

    let mut options = CopyOptions::new();
    options.overwrite = true;
    options.copy_inside = true;

    // Copy React UMD files
    if react_umd.exists() {
        copy_dir(&react_umd, &out_dir, &options).expect("Failed to copy react UMD files");
        println!("cargo:rerun-if-changed={}", react_umd.display());
    } else {
        println!("cargo:warning=React UMD directory not found: {}", react_umd.display());
    }

    // Copy ReactDOM UMD files
    if react_dom_umd.exists() {
        copy_dir(&react_dom_umd, &out_dir, &options).expect("Failed to copy react-dom UMD files");
        println!("cargo:rerun-if-changed={}", react_dom_umd.display());
    } else {
        println!("cargo:warning=ReactDOM UMD directory not found: {}", react_dom_umd.display());
    }
}
