# Changelog

All notable changes to the CI Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.9.5](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.4...v2.9.5) (2026-04-24)


### Bug Fixes

* replace pip-audit with pixi-native dependency audit ([b3fe618](https://github.com/Claire-s-Monster/ci-framework/commit/b3fe618e118455f20f67509dc094e2937f6b95d4))
* replace pip-audit with pixi-native dependency audit ([2b093c2](https://github.com/Claire-s-Monster/ci-framework/commit/2b093c2d44723b17b8ee964530454b09412fdde8))

## [2.9.4](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.3...v2.9.4) (2026-04-24)


### Bug Fixes

* remove internal security-events: write from reusable workflows ([41e8381](https://github.com/Claire-s-Monster/ci-framework/commit/41e83812f63457f8e60b10e9e2749d6b99c9dc37))
* remove security-events: write from reusable workflow job permissions ([8623317](https://github.com/Claire-s-Monster/ci-framework/commit/8623317121ca26959cf9ba263c1ffc77eabd0725))

## [2.9.3](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.2...v2.9.3) (2026-04-24)


### Bug Fixes

* eliminate security-events: write requirement for consumer repos ([4645ce9](https://github.com/Claire-s-Monster/ci-framework/commit/4645ce9666ff810514a4b136cbdf9121c1393a69))
* eliminate security-events: write requirement for consumer repos ([31b6759](https://github.com/Claire-s-Monster/ci-framework/commit/31b6759b111e9672f72a39584553ccc8370e1ea4))


### Documentation

* mark security-events: write as optional for Scorecard compliance ([021c51c](https://github.com/Claire-s-Monster/ci-framework/commit/021c51c2aac3913baa0c575fb67e78e62d5902a8))

## [2.9.2](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.1...v2.9.2) (2026-04-20)


### Bug Fixes

* add GITHUB_TOKEN fallback to release-please token ([b8ef39f](https://github.com/Claire-s-Monster/ci-framework/commit/b8ef39f4e6a314dd7a8aceb456f933a8c1bb7ccd))
* release automation token and reusable-ci permissions ([01ad23a](https://github.com/Claire-s-Monster/ci-framework/commit/01ad23a9216c0a22ce84584e733cba442bb17035))
* release automation tokens and Scorecard-safe permissions ([d95b337](https://github.com/Claire-s-Monster/ci-framework/commit/d95b337d5327347bc9b43438c598c4ac73d50254))
* scope write permissions per-job for Scorecard compliance ([0dafe1c](https://github.com/Claire-s-Monster/ci-framework/commit/0dafe1cd4aea5750bb426f96ab4748dbd7ee2a44))
* use CI_BOT_TOKEN for auto-merge and remove reusable-ci top-level permissions ([b4269e9](https://github.com/Claire-s-Monster/ci-framework/commit/b4269e92f992179cea3537f9950558a66161008b))
* use CI_BOT_TOKEN in release-please to avoid workflow approval gate ([ccce22c](https://github.com/Claire-s-Monster/ci-framework/commit/ccce22c8f29e00943d2a8a6c573f9d30adff544a))
* use CI_BOT_TOKEN in release-please to avoid workflow approval gate ([fc36d84](https://github.com/Claire-s-Monster/ci-framework/commit/fc36d84fcc9d77d076a6e0c846c010b6afffb769))


### Documentation

* show SHA pinning in reusable-ci usage example ([621d35e](https://github.com/Claire-s-Monster/ci-framework/commit/621d35e64f1548d387baee6b89c9ddc569a0f878))

## [2.9.1](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.0...v2.9.1) (2026-04-17)


### Bug Fixes

* scope security-events and id-token permissions per-job ([485e39f](https://github.com/Claire-s-Monster/ci-framework/commit/485e39f952f0a4f74e0638f45c421364315531c9))
* scope security-events and id-token permissions per-job ([6927a8d](https://github.com/Claire-s-Monster/ci-framework/commit/6927a8d45535b4f9fc2b5a9623edb3c7b97255ac))

## [2.9.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.8.0...v2.9.0) (2026-04-16)


### Features

* add optional PostgreSQL service container support ([eaa4a79](https://github.com/Claire-s-Monster/ci-framework/commit/eaa4a79891e6b3bc6876f47443b7af024f8f522c))
* add optional PostgreSQL service container support ([#164](https://github.com/Claire-s-Monster/ci-framework/issues/164)) ([e863745](https://github.com/Claire-s-Monster/ci-framework/commit/e863745399012cd6f317339b12194c1c317f4b38))


### Bug Fixes

* **tests:** exclude test-postgres from cross-file core job comparison ([4902059](https://github.com/Claire-s-Monster/ci-framework/commit/49020590208e0861204a996a457cbe6bbb7c64d7))

## [2.8.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.7.0...v2.8.0) (2026-04-13)


### Features

* accept [tool.pixi] in pyproject.toml + dependabot auto-merge ([556d878](https://github.com/Claire-s-Monster/ci-framework/commit/556d8780998bf0971ca682b2442980ceffb97ee9))
* accept [tool.pixi] in pyproject.toml as valid pixi config ([9c49a16](https://github.com/Claire-s-Monster/ci-framework/commit/9c49a16e0c2039530565e7256e4a6f02ce382957))

## [2.7.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.6.0...v2.7.0) (2026-04-11)


### Features

* add multi-language security and quality to reusable-ci.yml ([cc08477](https://github.com/Claire-s-Monster/ci-framework/commit/cc08477da9d4d4f955e2acf294f3974d62199923))
* add reusable-quality.yml with multi-language quality checks ([d4157a8](https://github.com/Claire-s-Monster/ci-framework/commit/d4157a8fa45b0f89d6afde8d983485e4dbc95fc8))
* add reusable-security.yml and reusable-quality.yml ([90788f9](https://github.com/Claire-s-Monster/ci-framework/commit/90788f9a315006f22daa0286a9aeab82dee6b9e0))
* add reusable-security.yml with language detection and dep audits ([115e421](https://github.com/Claire-s-Monster/ci-framework/commit/115e421fb1672a84cb75b37100ead036d67d324c))
* add SAST, secret scanning, scorecard to reusable-security.yml ([7f70ce7](https://github.com/Claire-s-Monster/ci-framework/commit/7f70ce729c3ad99f9e3b6e81d176e30a05a34760))
* automate release flow with auto-merge and main→development sync ([b21cc6a](https://github.com/Claire-s-Monster/ci-framework/commit/b21cc6ac30663be2c23fb0a9c6a7ca5395513444))
* automate release flow with auto-merge and sync-back ([9543da5](https://github.com/Claire-s-Monster/ci-framework/commit/9543da53bf10e1a8179bebf0078acf65c582a0de))
* inline multi-language security & quality into reusable-ci.yml ([4b7c75d](https://github.com/Claire-s-Monster/ci-framework/commit/4b7c75d47e4372ff1074644e7eee4e4cf88eaf07))


### Bug Fixes

* resolve shellcheck SC2144 — use compgen instead of -f with globs ([5995db4](https://github.com/Claire-s-Monster/ci-framework/commit/5995db4cc2bdb3b1fe813a6ce2d5f08220850999))


### Documentation

* add consumer documentation for multi-language CI ([d6b1d09](https://github.com/Claire-s-Monster/ci-framework/commit/d6b1d0931d91fb2597770d8588fe281d127ff14d))

## [2.6.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.5.1...v2.6.0) (2026-04-06)


### Features

* add annotation and summary formatters for code policy ([c977e31](https://github.com/Claire-s-Monster/ci-framework/commit/c977e31b8ed0f9529120d8e2e7c5e0b2860d5d41))
* add CLI entrypoint with exclude filtering and GitHub output ([2863b6c](https://github.com/Claire-s-Monster/ci-framework/commit/2863b6c6acf0945522cea91da88b106b5118b34e))
* add cyclomatic complexity check using radon ([6ab8ee1](https://github.com/Claire-s-Monster/ci-framework/commit/6ab8ee179825772aea02ba0f611405041f35b2b2))
* add data model and file length check for code policy ([2565143](https://github.com/Claire-s-Monster/ci-framework/commit/2565143352dad7b736006a2bf4bd75754c1657ba))
* add function length check using ast ([927874b](https://github.com/Claire-s-Monster/ci-framework/commit/927874bd1b76026f9abeb999647e496bbe1af7b7))
* add reusable code policy check workflow ([2e39e7f](https://github.com/Claire-s-Monster/ci-framework/commit/2e39e7fbd121c9e170239a08e09f45a36c2b6c71))
* add reusable-code-policy.yml workflow ([063da78](https://github.com/Claire-s-Monster/ci-framework/commit/063da782509209d7d68b03838cbe30d379a50f17))
* add vulture dead code detection to code policy check ([57958ca](https://github.com/Claire-s-Monster/ci-framework/commit/57958cad5948133a60dc833702741f81259374c4))
* add vulture dead code detection to reusable workflow ([2657d01](https://github.com/Claire-s-Monster/ci-framework/commit/2657d01ba201eb6beb74a9e7fdc5eb2163e98a1c))


### Bug Fixes

* add function-too-long to FileMetrics aggregation and summary table ([1fc9ec2](https://github.com/Claire-s-Monster/ci-framework/commit/1fc9ec2fa23582c3db168b8d1fc99e2983c98a5a))
* move cli_main and run_checks imports to top of test file (E402) ([2e233ac](https://github.com/Claire-s-Monster/ci-framework/commit/2e233acbdbdae09abd279626e78aa9c0a759c629))
* remove unused imports from code_policy_check.py ([591126f](https://github.com/Claire-s-Monster/ci-framework/commit/591126f68224f63ebba91354aba12881d5122232))
* resolve lint violations and CLI test reliability in CI ([8262090](https://github.com/Claire-s-Monster/ci-framework/commit/8262090b48dd668f48c9b2d00b3b94bceac42d9b))
* resolve ruff I001 import sorting and UP038 isinstance union ([be3df74](https://github.com/Claire-s-Monster/ci-framework/commit/be3df748d5eef83b7bae922b31fa01a3687846a8))
* target dependabot PRs to development branch instead of main ([83267f6](https://github.com/Claire-s-Monster/ci-framework/commit/83267f6589d61f7bfd1f767b65fc5fc1edfd1846))
* use in-process CLI tests and apply ruff formatting ([8880896](https://github.com/Claire-s-Monster/ci-framework/commit/88808968396a95fcc498c67afdefae57cbf836bd))


### Documentation

* add consumer documentation for code policy check ([2767310](https://github.com/Claire-s-Monster/ci-framework/commit/27673100708a8dbf24cb8f142830420639ba94c8))

## [2.5.1](https://github.com/Claire-s-Monster/ci-framework/compare/v2.5.0...v2.5.1) (2026-03-19)


### Bug Fixes

* split release workflow to prevent startup_failure ([6329885](https://github.com/Claire-s-Monster/ci-framework/commit/63298858f7897754fc3ca9d17a1c40737ea28927))
* split release workflow to prevent startup_failure in consumers ([cf48189](https://github.com/Claire-s-Monster/ci-framework/commit/cf481891005ae48031dc211f0e05ef38db69ddf6))


### Documentation

* add cross-reference to reusable-release.yml in header comment ([d431038](https://github.com/Claire-s-Monster/ci-framework/commit/d4310384d6db755d7a5b88a656977da4912562a1))

## [2.5.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.4.2...v2.5.0) (2026-03-17)


### Features

* standalone CI template, workflow linter, and dependency updates ([9d8fcdd](https://github.com/Claire-s-Monster/ci-framework/commit/9d8fcdd2a49c48afcb9ee394b4085d138ffbf966))


### Bug Fixes

* remove ci-framework runtime deps, add workflow validation ([#129](https://github.com/Claire-s-Monster/ci-framework/issues/129)) ([4a3f427](https://github.com/Claire-s-Monster/ci-framework/commit/4a3f427fd34c55a1615b8dfc4e5c04628b0892d3))

## [2.4.2](https://github.com/Claire-s-Monster/ci-framework/compare/v2.4.1...v2.4.2) (2026-03-05)


### Bug Fixes

* CI improvements for dependabot and push events ([#123](https://github.com/Claire-s-Monster/ci-framework/issues/123)) ([73e1476](https://github.com/Claire-s-Monster/ci-framework/commit/73e1476ede9216f840bea96efb1a49cca134e205))

## [2.4.1](https://github.com/Claire-s-Monster/ci-framework/compare/v2.4.0...v2.4.1) (2026-02-14)


### Bug Fixes

* sync security scan CLI fix to main ([6e02808](https://github.com/Claire-s-Monster/ci-framework/commit/6e028088a5fbda931315344efd2da39f10249dd1))
* use positional argument for security scan CLI ([#113](https://github.com/Claire-s-Monster/ci-framework/issues/113)) ([a9f62bf](https://github.com/Claire-s-Monster/ci-framework/commit/a9f62bf0ff83f1c1232f254a9ba0506b69b7b2c9)), closes [#112](https://github.com/Claire-s-Monster/ci-framework/issues/112)

## [2.4.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.3.2...v2.4.0) (2026-02-14)


### Features

* convert Gemini AI workflow to reusable workflow ([#109](https://github.com/Claire-s-Monster/ci-framework/issues/109)) ([02ee684](https://github.com/Claire-s-Monster/ci-framework/commit/02ee684d8b6d7d3c0076d5f4eafb02ea7e230c93))

## [2.3.2](https://github.com/Claire-s-Monster/ci-framework/compare/v2.3.1...v2.3.2) (2026-02-14)


### Bug Fixes

* use absolute GITHUB_WORKSPACE path for framework CLI scripts ([#106](https://github.com/Claire-s-Monster/ci-framework/issues/106)) ([f94ac13](https://github.com/Claire-s-Monster/ci-framework/commit/f94ac13d189a90fdf3a9be4013e48777fe54ab8e))

## [2.3.1](https://github.com/Claire-s-Monster/ci-framework/compare/v2.3.0...v2.3.1) (2026-02-13)


### Bug Fixes

* clarify workflow usage patterns and add pyyaml dependency ([#100](https://github.com/Claire-s-Monster/ci-framework/issues/100)) ([246bdd9](https://github.com/Claire-s-Monster/ci-framework/commit/246bdd993eb92cb8db6430494c420ccce730167f))

## [2.3.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.2.0...v2.3.0) (2026-01-05)


### Features

* **ci:** add manual GitHub Pages deployment workflow ([#70](https://github.com/Claire-s-Monster/ci-framework/issues/70)) ([fd4ba63](https://github.com/Claire-s-Monster/ci-framework/commit/fd4ba63f59295cab3aa3b504c321a7df9d6b15cb))


### Bug Fixes

* **ci:** add enablement parameter to auto-enable GitHub Pages ([#73](https://github.com/Claire-s-Monster/ci-framework/issues/73)) ([b61a9a4](https://github.com/Claire-s-Monster/ci-framework/commit/b61a9a4379816c50db700d36b7a18fcbc7c74573))

## [2.2.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.1.0...v2.2.0) (2025-12-30)


### Features

* **ci:** add GPG signing for Release Please commits ([#66](https://github.com/Claire-s-Monster/ci-framework/issues/66)) ([7af0421](https://github.com/Claire-s-Monster/ci-framework/commit/7af042142acbcaed24a5c01d9d5fa3782c11b7dd))


### Bug Fixes

* **ci:** remove invalid 'releases' permission from release-please workflow ([#64](https://github.com/Claire-s-Monster/ci-framework/issues/64)) ([3bb3112](https://github.com/Claire-s-Monster/ci-framework/commit/3bb31120c5ed649ae2624ac8b9dbbb83f3bed6b3))
* **ci:** update cleanup workflow ref from deleted branch to main ([#68](https://github.com/Claire-s-Monster/ci-framework/issues/68)) ([bb4193a](https://github.com/Claire-s-Monster/ci-framework/commit/bb4193abecb6f76974a4cccf6b216c37da7c1a06))
* **ci:** use inline GPG import instead of external action ([#67](https://github.com/Claire-s-Monster/ci-framework/issues/67)) ([4c5bfdd](https://github.com/Claire-s-Monster/ci-framework/commit/4c5bfddb751a562f4b716a953cb833c32ec90380))

## [Unreleased]

## [2.1.0] - 2025-08-08

### 🚀 Features

- Self-Healing CI infrastructure with automated failure detection and fixes
- Safe rollback capabilities with git state preservation
- Comprehensive documentation and API reference for Self-Healing actions
- Enterprise-grade GPG-signed commits and audit trails
- Release Please automation for CHANGELOG generation

### 📚 Documentation

- Complete Self-Healing CI documentation with usage examples
- API reference documentation for all Self-Healing capabilities
- Best practices guides for integration patterns and safety features
- Updated README with workflow catalog and usage examples
- GitHub Pages deployment automation

### 🔧 Maintenance

- Repository cleanup with __pycache__ file purge
- Version bump to v2.1.0 for Self-Healing CI feature release
- Release Please automation setup for future releases
- PIXI environment optimizations

## [2.0.0] - 2024-12-XX

### 🚀 Features

- Comprehensive enterprise-grade CI automation framework
- Intelligent CI optimization with 50%+ time savings through smart change detection
- Multi-layered security with comprehensive vulnerability scanning and SBOM generation
- Cross-platform excellence with native pixi dependency resolution
- Automated repository hygiene with GPG-signed cleanup
- Standardized quality gates with zero-tolerance policy
- AI-development ready handling Claude, TaskMaster, Cursor, and Aider artifacts

### 📚 Documentation

- Complete framework documentation with API references
- Best practices guides for all major features
- Interactive examples and tutorials
- Migration guides and compatibility documentation

### 👷 CI/CD

- Quality gates with tiered environments (essential, extended, full)
- Performance monitoring with statistical regression detection
- Security scanning with SARIF integration
- Cross-platform validation workflows
- Cleanup automation for development artifacts

---

*This changelog is automatically generated by [Release Please](https://github.com/googleapis/release-please).*
