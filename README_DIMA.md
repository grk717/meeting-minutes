### For macOS:

1. Install prerequisites:
   ```bash
   # Install Homebrew if not already installed
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Install Node.js
   brew install node
   
   # Install Rust
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   
   # Install pnpm
   npm install -g pnpm
   
   # Install Xcode Command Line Tools
   xcode-select --install
   ```

2. Clone the repository and navigate to the frontend directory:
   ```bash
   git clone https://github.com/grk717/meeting-minutes
   cd meeting-minutes/frontend
   ```
  

3. Install dependencies:
   ```bash
   pnpm install
   ```


Use the provided script to run the app in development mode:
```bash
./clean_run.sh
```

To build a production version:
```bash
./clean_build.sh
```