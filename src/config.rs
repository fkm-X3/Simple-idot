pub struct IdotConfig {
    pub version: &'static str,
    #[allow(dead_code)] // don't feel like removing this
    pub ignore_docs: bool, // whether to ignore ~ comments in the token stream
    #[allow(dead_code)] // same here
    pub allow_external_res: bool, // whether to allow external resources (bring(py) or bring(js))
}

impl IdotConfig {
    pub fn default() -> Self {
        Self {
            version: "0.1.0",
            ignore_docs: true,      // set to false if you want to include ~ comments in the token stream
            allow_external_res: true,
        }
    }
}