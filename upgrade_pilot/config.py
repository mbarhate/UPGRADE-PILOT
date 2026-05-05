"""Configuration values for Upgrade-Pilot.

This module contains the LANGUAGE_CONFIG dictionary that defines build, test,
install commands, file extensions, and research context for each supported
programming language and tech stack. The configuration enables Upgrade-Pilot
to work polyglot-ready across Node.js, Python, Java, Go, Rust, PHP, Ruby,
.NET, and Cordova projects.

Each language entry includes:
    - manifest: The dependency/build manifest filename pattern.
    - install_cmd: Shell command to install dependencies.
    - build_cmd: Shell command to compile/build the project.
    - test_cmd: Shell command to run tests.
    - extensions: List of source file extensions for the language.
    - research_context: LLM prompt hint for breaking changes research.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validate required environment variables
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is not set.")
    print("Please copy .env.example to .env and fill in your GitHub PAT.")
    sys.exit(1)

LANGUAGE_CONFIG = {
    "nodejs": {
        "manifest": "package.json",
        "install_cmd": "npm install",
        "build_cmd": "npm run build",
        "test_cmd": "npm test",
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "research_context": "npm ecosystem and CommonJS/ESM modules",
    },
    "python": {
        "manifest": "requirements.txt",  # or pyproject.toml
        "install_cmd": "pip install -r requirements.txt",
        "build_cmd": "python -m py_compile **/*.py",
        "test_cmd": "pytest",
        "extensions": [".py"],
        "research_context": "PyPI and PEP standards",
    },
    "java_maven": {
        "manifest": "pom.xml",
        "install_cmd": "mvn install -DskipTests",
        "build_cmd": "mvn compile",
        "test_cmd": "mvn test",
        "extensions": [".java"],
        "research_context": "Maven Central and JRE/JDK compatibility",
    },
    "java_gradle": {
        "manifest": "build.gradle",
        "install_cmd": "./gradlew build -x test",
        "build_cmd": "./gradlew assemble",
        "test_cmd": "./gradlew test",
        "extensions": [".java", ".kts"],
        "research_context": "Gradle plugins and Groovy/Kotlin DSL",
    },
    "dotnet": {
        "manifest": "*.csproj",
        "install_cmd": "dotnet restore",
        "build_cmd": "dotnet build",
        "test_cmd": "dotnet test",
        "extensions": [".cs"],
        "research_context": "NuGet and .NET Core/Framework versions",
    },
    "go": {
        "manifest": "go.mod",
        "install_cmd": "go mod download",
        "build_cmd": "go build ./...",
        "test_cmd": "go test ./...",
        "extensions": [".go"],
        "research_context": "Go modules and Gopath",
    },
    "php": {
        "manifest": "composer.json",
        "install_cmd": "composer install",
        "build_cmd": "php -l src/**/*.php",
        "test_cmd": "vendor/bin/phpunit",
        "extensions": [".php"],
        "research_context": "Composer and Packagist",
    },
    "ruby": {
        "manifest": "Gemfile",
        "install_cmd": "bundle install",
        "build_cmd": "ruby -c **/*.rb",
        "test_cmd": "bundle exec rake test",
        "extensions": [".rb"],
        "research_context": "RubyGems and Bundler",
    },
    "rust": {
        "manifest": "Cargo.toml",
        "install_cmd": "cargo fetch",
        "build_cmd": "cargo build",
        "test_cmd": "cargo test",
        "extensions": [".rs"],
        "research_context": "Crates.io and Rust Ownership/Borrowing rules",
    },
    "cordova": {
        "manifest": "config.xml",
        "install_cmd": "npm install && cordova prepare",
        "build_cmd": "cordova build browser",
        "test_cmd": "npm test",
        "extensions": [".js", ".html", ".css"],
        "research_context": "Cordova plugins and WebView bridge",
    },
}
