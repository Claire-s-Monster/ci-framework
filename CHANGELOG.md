# Changelog

All notable changes to the CI Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.2.1](https://github.com/Claire-s-Monster/ci-framework/compare/v4.2.0...v4.2.1) (2026-11-09)


### 🐛 Bug Fixes

* **pixi-lock-refresh:** validate App credentials on every run ([12ad010](https://github.com/Claire-s-Monster/ci-framework/commit/12ad010b55a49e0546f1c2aad5f030b194f5b752))
* **pixi-lock-refresh:** validate App credentials on every run ([8f9339f](https://github.com/Claire-s-Monster/ci-framework/commit/8f9339f9a8f99b9f4ecfdd2c106eb07a5afc8d9e))


### 🔧 Maintenance

* sync main back to development ([a3a7168](https://github.com/Claire-s-Monster/ci-framework/commit/a3a716860c082ae7cee329579f5df40533eb54bb))


### 🧪 Tests

* **pixi-lock-refresh:** accept any pinned semver for Dependabot-managed actions ([dbf3fe9](https://github.com/Claire-s-Monster/ci-framework/commit/dbf3fe945c4ebcf2bcb54f54b8040a5c9f78f278))
* **pixi-lock-refresh:** accept any pinned semver for Dependabot-managed actions ([a871f24](https://github.com/Claire-s-Monster/ci-framework/commit/a871f2410c39a69a9c716f7680e2125d3e0b009f))


### 👷 CI/CD

* **deps:** bump prefix-dev/setup-pixi from 0.11.2 to 0.11.3 ([#415](https://github.com/Claire-s-Monster/ci-framework/issues/415)) ([cc0d81e](https://github.com/Claire-s-Monster/ci-framework/commit/cc0d81e2d872a0ea667ab255b2b3a8be74e599e6))
* **deps:** bump prefix-dev/setup-pixi in /actions/change-detection ([#418](https://github.com/Claire-s-Monster/ci-framework/issues/418)) ([0b0333b](https://github.com/Claire-s-Monster/ci-framework/commit/0b0333bc1b5123ea2447e4f5fbc8040dece34d56))
* **deps:** bump prefix-dev/setup-pixi in /actions/performance-benchmark ([#417](https://github.com/Claire-s-Monster/ci-framework/issues/417)) ([7d17f58](https://github.com/Claire-s-Monster/ci-framework/commit/7d17f58d13452b63bc565d75b980ea465fae540b))
* **deps:** bump prefix-dev/setup-pixi in /actions/quality-gates ([#419](https://github.com/Claire-s-Monster/ci-framework/issues/419)) ([2bfbbe7](https://github.com/Claire-s-Monster/ci-framework/commit/2bfbbe710caf1dd4e3973234ae3351ded0bab7d8))
* **deps:** bump prefix-dev/setup-pixi in /actions/security-scan ([#420](https://github.com/Claire-s-Monster/ci-framework/issues/420)) ([e2c5d6d](https://github.com/Claire-s-Monster/ci-framework/commit/e2c5d6dcac110ad47e1025bed7d456538159f5e8))
* **deps:** bump prefix-dev/setup-pixi in /actions/self-healing ([#421](https://github.com/Claire-s-Monster/ci-framework/issues/421)) ([4fb2c78](https://github.com/Claire-s-Monster/ci-framework/commit/4fb2c781a37196e7ec77b7f51d0ae4a6453fecef))
* **deps:** bump trufflesecurity/trufflehog from 3.99.7 to 3.99.8 ([4c3607a](https://github.com/Claire-s-Monster/ci-framework/commit/4c3607a70a1cf5f45a387d1a55a6d585f16ea488))
* **deps:** bump trufflesecurity/trufflehog from 3.99.7 to 3.99.8 ([e310b01](https://github.com/Claire-s-Monster/ci-framework/commit/e310b01da573b54fb64aa423e5b65ba39ee0fb7b))

## [4.2.0](https://github.com/Claire-s-Monster/ci-framework/compare/v4.1.0...v4.2.0) (2026-11-05)


### 🚀 Features

* **pixi-lock-refresh:** optional GitHub App token, read-only caller ([#406](https://github.com/Claire-s-Monster/ci-framework/issues/406)) ([2c40404](https://github.com/Claire-s-Monster/ci-framework/commit/2c40404ce554fadb75a7beed0a6cc5f1cf30e2d7))
* **pixi-lock-refresh:** optional GitHub App token, read-only caller ([#406](https://github.com/Claire-s-Monster/ci-framework/issues/406)) ([b791010](https://github.com/Claire-s-Monster/ci-framework/commit/b791010328800fc92e19114df03960066080574b))


### 🐛 Bug Fixes

* **cleanup:** run cleanup once per push and skip the release commit ([3fe5971](https://github.com/Claire-s-Monster/ci-framework/commit/3fe5971cf794b27d94d102c6fab9c2e31d997e12))
* **cleanup:** run cleanup once per push and skip the release commit ([2a7cd5e](https://github.com/Claire-s-Monster/ci-framework/commit/2a7cd5e90663d5c36ab136ee026ee9328dbf9733))
* **sync:** skip main-&gt;development sync when the trees are identical ([bbfeb56](https://github.com/Claire-s-Monster/ci-framework/commit/bbfeb56599aa7e8df68031b32d645bae70e47fac))
* **sync:** skip main-&gt;development sync when the trees are identical ([4ba6df6](https://github.com/Claire-s-Monster/ci-framework/commit/4ba6df61965ac858680cafb8c905ca751201bea1))


### 📚 Documentation

* **lock-refresh:** explain Scorecard Token-Permissions alerts on the caller ([b82ef42](https://github.com/Claire-s-Monster/ci-framework/commit/b82ef4233961d86c98663ef8255b35edde3e190e))
* **lock-refresh:** explain Scorecard Token-Permissions alerts on the caller ([40bb0ab](https://github.com/Claire-s-Monster/ci-framework/commit/40bb0ab569ced8aa5d289ebe4aded002956ee81b))


### 🔧 Maintenance

* sync main back to development ([fc11dc7](https://github.com/Claire-s-Monster/ci-framework/commit/fc11dc777f271337d44e0e02244a4393e434223b))


### 👷 CI/CD

* add concurrency groups to push-triggered workflows ([a613a23](https://github.com/Claire-s-Monster/ci-framework/commit/a613a235cdc8f2f029d36fe08be7dd560e3b8122))
* add concurrency groups to push-triggered workflows ([b110116](https://github.com/Claire-s-Monster/ci-framework/commit/b110116bc08bc7fb3cc30ed69b15e61f6023b036))

## [4.1.0](https://github.com/Claire-s-Monster/ci-framework/compare/v4.0.0...v4.1.0) (2026-11-04)


### 🚀 Features

* **deps:** reusable scheduled pixi.lock refresh workflow ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([22f228b](https://github.com/Claire-s-Monster/ci-framework/commit/22f228bc88e9ec689dff2e49e750d5f522a2a4c4))
* **deps:** reusable scheduled pixi.lock refresh workflow ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([3f2450f](https://github.com/Claire-s-Monster/ci-framework/commit/3f2450f23d8481c85a2bea0a6cee22427341724f))
* **pixi-lock-refresh:** run on github.token with zero secrets ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([1e9665a](https://github.com/Claire-s-Monster/ci-framework/commit/1e9665a7c462dcbf5c9ab7a9957aff262bd48c2d))
* **pixi-lock-refresh:** run on github.token with zero secrets ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([c3015c9](https://github.com/Claire-s-Monster/ci-framework/commit/c3015c9b4ffa1f718500bfb1fd64be1085ee03f0))
* **release:** track fixed-in-development issues across releases ([#394](https://github.com/Claire-s-Monster/ci-framework/issues/394)) ([9a8871b](https://github.com/Claire-s-Monster/ci-framework/commit/9a8871b9c372b933e174f08f03ee05f52389f040))
* **release:** track fixed-in-development issues across releases ([#394](https://github.com/Claire-s-Monster/ci-framework/issues/394)) ([13b6f61](https://github.com/Claire-s-Monster/ci-framework/commit/13b6f6132bce2987025b7100acd6660433750cdc))
* **reusable-ci:** opt-in pip-policy check for extras and bare pip install ([#399](https://github.com/Claire-s-Monster/ci-framework/issues/399)) ([63e76e0](https://github.com/Claire-s-Monster/ci-framework/commit/63e76e0abaf85b803e35f86181e3cc628111fac3))
* **reusable-ci:** opt-in pip-policy check for extras and bare pip install ([#399](https://github.com/Claire-s-Monster/ci-framework/issues/399)) ([a0dc109](https://github.com/Claire-s-Monster/ci-framework/commit/a0dc109e81e933e22e8e9bdcff380e1f62d47720))


### 🐛 Bug Fixes

* **ci:** install Semgrep via pip instead of Docker Hub container ([#366](https://github.com/Claire-s-Monster/ci-framework/issues/366)) ([a09e3ba](https://github.com/Claire-s-Monster/ci-framework/commit/a09e3bad732da9c13c3d5df1c645bd6c3540c149))
* **ci:** install Semgrep via pip instead of Docker Hub container ([#366](https://github.com/Claire-s-Monster/ci-framework/issues/366)) ([ade9575](https://github.com/Claire-s-Monster/ci-framework/commit/ade9575f24d8b72e4119a92e7ca748c5c2d8b4f0))
* **deps:** raise security floors to clear 34 pip-audit findings ([5c835f7](https://github.com/Claire-s-Monster/ci-framework/commit/5c835f702e30dfd98000747bf73ca641c1518259))
* **deps:** raise security floors to clear 34 pip-audit findings ([ee55930](https://github.com/Claire-s-Monster/ci-framework/commit/ee5593010a168674dcd91565ea29f91107e7ed20))
* **gemini:** skip AI analysis on quota/billing errors instead of failing ([cd67d67](https://github.com/Claire-s-Monster/ci-framework/commit/cd67d671a8839abe97f67aa566e161024919f85b))
* **gemini:** skip AI analysis on quota/billing errors instead of failing ([1516a8a](https://github.com/Claire-s-Monster/ci-framework/commit/1516a8a0e5c47b7c16a47ffa26f864e4c7ea49de))
* **pip-policy:** address [#400](https://github.com/Claire-s-Monster/ci-framework/issues/400) review: flags before -e, continuations, property escaping, python guard ([1d39599](https://github.com/Claire-s-Monster/ci-framework/commit/1d3959948ed23044e2c347d82629111dd02d8e97))
* **pip-policy:** ignore pip mentions in trailing shell comments ([#400](https://github.com/Claire-s-Monster/ci-framework/issues/400) review) ([e983ff7](https://github.com/Claire-s-Monster/ci-framework/commit/e983ff759959e1b16b825b2edd318a69b9279f2f))
* **pip-policy:** report an unreadable pyproject instead of crashing ([#400](https://github.com/Claire-s-Monster/ci-framework/issues/400) review) ([3fe82c1](https://github.com/Claire-s-Monster/ci-framework/commit/3fe82c1955086426074a00d4779dc7e44c39a7ae))
* **pixi-lock-refresh:** clearer dispatch error, log request size ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([f476c0a](https://github.com/Claire-s-Monster/ci-framework/commit/f476c0a176195e9a118f2267d6669532d91f2240))
* **pixi-lock-refresh:** delete the temp ref on a cancelled run ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([9fa3a99](https://github.com/Claire-s-Monster/ci-framework/commit/9fa3a992e7d787a636899ebdbc77510e95b9c121))
* **pixi-lock-refresh:** use GITHUB_API_URL in the token preflight ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([ba9fcf3](https://github.com/Claire-s-Monster/ci-framework/commit/ba9fcf3b9ac91a959090f983b11917b0d31a4884))
* **release:** stop release-type input overriding release-please config ([#390](https://github.com/Claire-s-Monster/ci-framework/issues/390)) ([fedcf8f](https://github.com/Claire-s-Monster/ci-framework/commit/fedcf8f1215176503ba065c126a586e98a48ea72))
* **release:** stop release-type input overriding release-please config ([#390](https://github.com/Claire-s-Monster/ci-framework/issues/390)) ([0063ecc](https://github.com/Claire-s-Monster/ci-framework/commit/0063ecce003a6065672ae0350627bf44658be2fe))
* **reusable-ci:** CI Summary must prove gated jobs ran ([#385](https://github.com/Claire-s-Monster/ci-framework/issues/385)) ([556b8ac](https://github.com/Claire-s-Monster/ci-framework/commit/556b8acb66850be87180bf10d5d14da956fe75d1))
* **reusable-ci:** CI Summary must prove gated jobs ran ([#385](https://github.com/Claire-s-Monster/ci-framework/issues/385)) ([5702661](https://github.com/Claire-s-Monster/ci-framework/commit/57026614cd9f54d913465ef64465b359ec7db2eb))
* **reusable-ci:** enforce conda-first dependencies ([#386](https://github.com/Claire-s-Monster/ci-framework/issues/386)) ([39ddbe0](https://github.com/Claire-s-Monster/ci-framework/commit/39ddbe0f8fb7a9380e4ba723da0bae701be2d472))
* **reusable-ci:** enforce conda-first dependencies ([#386](https://github.com/Claire-s-Monster/ci-framework/issues/386)) ([7a35886](https://github.com/Claire-s-Monster/ci-framework/commit/7a358863f5220a076f0627c90d4853ac4ea9621f))
* **scorecard:** run only on pull_request or the default branch ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([a018214](https://github.com/Claire-s-Monster/ci-framework/commit/a01821468dcea9937a38be1fb5bffba65052e351))
* **scorecard:** run only on pull_request or the default branch ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([ef37208](https://github.com/Claire-s-Monster/ci-framework/commit/ef372083ae573ff42060c1ce18a81b8c80e73d81))
* **security-scan:** pin Semgrep to 1.180.0 ([593fb88](https://github.com/Claire-s-Monster/ci-framework/commit/593fb885d64d21c0c4c3507e41fc2cde984eb21e))
* **security-scan:** pin Semgrep to 1.180.0 ([8da1b08](https://github.com/Claire-s-Monster/ci-framework/commit/8da1b08b60be3aa91b57abf1444d2caa57da9005))
* **test:** narrow regex match before .group() in release-please guard ([b59b330](https://github.com/Claire-s-Monster/ci-framework/commit/b59b330fbda08e8d3ded19f288afc83da916d29d))


### 🔧 Maintenance

* sync main back to development ([7cbdd79](https://github.com/Claire-s-Monster/ci-framework/commit/7cbdd79d2803f2058e8fb61f394e2e20bf477ef3))


### 🧪 Tests

* **scorecard:** match the exact ref gate, not loose substrings ([#387](https://github.com/Claire-s-Monster/ci-framework/issues/387)) ([b101238](https://github.com/Claire-s-Monster/ci-framework/commit/b101238202df14ab1c75c196f0cdc8af96929ef3))


### 👷 CI/CD

* **cython-lint:** bump setup-pixi to v0.11.2 to match other jobs ([7f8e311](https://github.com/Claire-s-Monster/ci-framework/commit/7f8e311af88597c1270d1f100ce17daa1520b2b2))
* **deps:** bump Claire-s-Monster/ci-framework from 3.0.0 to 4.0.0 ([bb65b16](https://github.com/Claire-s-Monster/ci-framework/commit/bb65b1622ea11344204f4f4a86b873e3c2c1eeeb))
* **deps:** bump Claire-s-Monster/ci-framework from 3.0.0 to 4.0.0 ([0d560a5](https://github.com/Claire-s-Monster/ci-framework/commit/0d560a5654cc988915f259989a81800696cf95bb))
* **deps:** bump ossf/scorecard-action from 2.4.4 to 2.5.0 ([#377](https://github.com/Claire-s-Monster/ci-framework/issues/377)) ([3d5a5e4](https://github.com/Claire-s-Monster/ci-framework/commit/3d5a5e4d97a42c53b18afe57a9e97209fd209842))
* **deps:** bump prefix-dev/setup-pixi from 0.10.2 to 0.11.0 ([#371](https://github.com/Claire-s-Monster/ci-framework/issues/371)) ([356c176](https://github.com/Claire-s-Monster/ci-framework/commit/356c17671e7a1d1ea3731baa9070a18f098dce35))
* **deps:** bump prefix-dev/setup-pixi from 0.11.0 to 0.11.2 ([#378](https://github.com/Claire-s-Monster/ci-framework/issues/378)) ([bf02930](https://github.com/Claire-s-Monster/ci-framework/commit/bf02930c3b305dda10189b84057ff80e7a6247f2))
* **deps:** bump prefix-dev/setup-pixi in /actions/change-detection ([#373](https://github.com/Claire-s-Monster/ci-framework/issues/373)) ([ff98cb1](https://github.com/Claire-s-Monster/ci-framework/commit/ff98cb1ccded3a267bf7f8a008995510747ce896))
* **deps:** bump prefix-dev/setup-pixi in /actions/change-detection ([#380](https://github.com/Claire-s-Monster/ci-framework/issues/380)) ([3a9901d](https://github.com/Claire-s-Monster/ci-framework/commit/3a9901df1fd4ef834b75e40c5bf5be0f208fc98a))
* **deps:** bump prefix-dev/setup-pixi in /actions/performance-benchmark ([#375](https://github.com/Claire-s-Monster/ci-framework/issues/375)) ([b0a0d22](https://github.com/Claire-s-Monster/ci-framework/commit/b0a0d22cd8d5ab6c8d4faf87630b8bacea549a01))
* **deps:** bump prefix-dev/setup-pixi in /actions/performance-benchmark ([#381](https://github.com/Claire-s-Monster/ci-framework/issues/381)) ([1e52c31](https://github.com/Claire-s-Monster/ci-framework/commit/1e52c31d01f4fca37c52be6caeb8f063fcfc9b37))
* **deps:** bump prefix-dev/setup-pixi in /actions/quality-gates ([#376](https://github.com/Claire-s-Monster/ci-framework/issues/376)) ([41dfb72](https://github.com/Claire-s-Monster/ci-framework/commit/41dfb72206f345d85cfa28f8cee28cbd8a2bae5c))
* **deps:** bump prefix-dev/setup-pixi in /actions/quality-gates ([#382](https://github.com/Claire-s-Monster/ci-framework/issues/382)) ([c12fb17](https://github.com/Claire-s-Monster/ci-framework/commit/c12fb1759fc87db7bf6159620c292817dc00f983))
* **deps:** bump prefix-dev/setup-pixi in /actions/security-scan ([#372](https://github.com/Claire-s-Monster/ci-framework/issues/372)) ([07b62f3](https://github.com/Claire-s-Monster/ci-framework/commit/07b62f319d161643bba0558f0bf7f43b8dbffaae))
* **deps:** bump prefix-dev/setup-pixi in /actions/security-scan ([#383](https://github.com/Claire-s-Monster/ci-framework/issues/383)) ([781fae2](https://github.com/Claire-s-Monster/ci-framework/commit/781fae2a8a98a552b670573a3cf5043e465fca7b))
* **deps:** bump prefix-dev/setup-pixi in /actions/self-healing ([#374](https://github.com/Claire-s-Monster/ci-framework/issues/374)) ([52ab63a](https://github.com/Claire-s-Monster/ci-framework/commit/52ab63a84c98a10dccac748934e61f69ffc0070f))
* **deps:** bump prefix-dev/setup-pixi in /actions/self-healing ([#379](https://github.com/Claire-s-Monster/ci-framework/issues/379)) ([76ff0ff](https://github.com/Claire-s-Monster/ci-framework/commit/76ff0ffd75069b407882461bcc31fda83ce5c4c3))
* **deps:** bump trufflesecurity/trufflehog from 3.97.9 to 3.99.2 ([#369](https://github.com/Claire-s-Monster/ci-framework/issues/369)) ([fce9317](https://github.com/Claire-s-Monster/ci-framework/commit/fce93170bc8f2078fee10f35812704296bc081c9))
* **deps:** bump trufflesecurity/trufflehog from 3.99.2 to 3.99.7 ([#384](https://github.com/Claire-s-Monster/ci-framework/issues/384)) ([110f526](https://github.com/Claire-s-Monster/ci-framework/commit/110f526ed84a8eed1e7e5b75fb9dbd389f79d65a))

## [4.0.0](https://github.com/Claire-s-Monster/ci-framework/compare/v3.0.0...v4.0.0) (2026-10-06)


### ⚠ BREAKING CHANGES

* **gpg-signing-setup:** gpg-signing-setup's config-scope now defaults to 'local'. Callers that run it before actions/checkout, or that commit from a different repository than the current directory, must pass

### Bug Fixes

* **ci:** document CI_BOT_TOKEN as required where SARIF auth needs it ([d2501eb](https://github.com/Claire-s-Monster/ci-framework/commit/d2501ebe88af27c844a334db76696c2475e18f1b))
* **ci:** document CI_BOT_TOKEN as required where SARIF auth needs it ([71c324f](https://github.com/Claire-s-Monster/ci-framework/commit/71c324f80b59895fb79d0c033098a8ac7e7d42d9)), closes [#352](https://github.com/Claire-s-Monster/ci-framework/issues/352)
* **ci:** drop dead c-cpp-lint SARIF upload and its narrowing block ([fa8bd22](https://github.com/Claire-s-Monster/ci-framework/commit/fa8bd22d9baa632910b8c45e565ddd54da5454d7))
* **ci:** drop dead c-cpp-lint SARIF upload and its narrowing block ([8a04645](https://github.com/Claire-s-Monster/ci-framework/commit/8a046456dcb1e798965e0faf377b3c00481848d3)), closes [#354](https://github.com/Claire-s-Monster/ci-framework/issues/354)
* **ci:** drop matrix vars from job names so skipped jobs read correctly ([4f49a50](https://github.com/Claire-s-Monster/ci-framework/commit/4f49a5003f6f8092bef235e71611185742626c28))
* **ci:** drop matrix vars from job names so skipped jobs read correctly ([061b1d6](https://github.com/Claire-s-Monster/ci-framework/commit/061b1d69526e6f6b6dc00e89cbd3011da238762b)), closes [#339](https://github.com/Claire-s-Monster/ci-framework/issues/339)
* **ci:** drop unused GPG setup and checkout from release-please ([10f47cb](https://github.com/Claire-s-Monster/ci-framework/commit/10f47cbe3b1e179948b7c8bd37a091add0ac6f5b))
* **ci:** drop unused GPG setup and checkout from release-please ([e030abd](https://github.com/Claire-s-Monster/ci-framework/commit/e030abd40022d1c98dbc5d9a7372ffb75b0f6ac5)), closes [#348](https://github.com/Claire-s-Monster/ci-framework/issues/348)
* **ci:** fail fast when CI_BOT_TOKEN is set but invalid ([7062ea4](https://github.com/Claire-s-Monster/ci-framework/commit/7062ea4a49b770b9d4ab1952a6fd5af2ef28aa4d))
* **ci:** fail fast when CI_BOT_TOKEN is set but invalid ([f9bd956](https://github.com/Claire-s-Monster/ci-framework/commit/f9bd956e6eaf920b0738212430f3076ca8e4bd9b)), closes [#355](https://github.com/Claire-s-Monster/ci-framework/issues/355)
* **ci:** keep scorecard jobs publishable; time-limit the token check ([b90d280](https://github.com/Claire-s-Monster/ci-framework/commit/b90d280c0960df949044a76bc8ca9003f11be74c)), closes [#355](https://github.com/Claire-s-Monster/ci-framework/issues/355)
* **ci:** let scorecard inherit the caller's grant; CI_BOT_TOKEN optional ([769417e](https://github.com/Claire-s-Monster/ci-framework/commit/769417e51387a3d6b86a48a06f2f6ceb88c41af0))
* **ci:** let scorecard inherit the caller's grant; CI_BOT_TOKEN optional ([c746746](https://github.com/Claire-s-Monster/ci-framework/commit/c7467464dbea1c4a11d068134e1be205b0b6d062)), closes [#353](https://github.com/Claire-s-Monster/ci-framework/issues/353)
* **ci:** let the 3 SAST jobs inherit the caller's SARIF permission ([df4e552](https://github.com/Claire-s-Monster/ci-framework/commit/df4e552be9b29a1ccb6da0fcd18309c644424c75))
* **ci:** let the 3 SAST jobs inherit the caller's SARIF permission ([6494239](https://github.com/Claire-s-Monster/ci-framework/commit/64942390998cd890a3513e8ab08c98942dbedcab)), closes [#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)
* **ci:** scope write tokens to jobs; guard top-level permissions ([#359](https://github.com/Claire-s-Monster/ci-framework/issues/359)) ([11ec293](https://github.com/Claire-s-Monster/ci-framework/commit/11ec2938f25ea64922d58c16bab986b3714267ee))
* **ci:** scope write tokens to jobs; guard top-level permissions ([#359](https://github.com/Claire-s-Monster/ci-framework/issues/359)) ([e878c9c](https://github.com/Claire-s-Monster/ci-framework/commit/e878c9c49c9a35bce1d2eac19b36ddd5f8129157))
* **ci:** stop writing CI_BOT_TOKEN into --global git config ([c04f801](https://github.com/Claire-s-Monster/ci-framework/commit/c04f801db3a4f9d848feb43b800663460dd58e4b))
* **ci:** stop writing CI_BOT_TOKEN into --global git config ([929f5a4](https://github.com/Claire-s-Monster/ci-framework/commit/929f5a419470daeaa568e210e278d17699c995eb)), closes [#345](https://github.com/Claire-s-Monster/ci-framework/issues/345)
* **deps:** raise urllib3 and virtualenv floors past new advisories ([293567f](https://github.com/Claire-s-Monster/ci-framework/commit/293567fad78f7fe6a82e9099a4ea6ea814b2ff99))
* **deps:** raise urllib3 and virtualenv floors past new advisories ([ceec921](https://github.com/Claire-s-Monster/ci-framework/commit/ceec92195475328d63814ee978700c925d6623b5))
* **gpg-signing-setup:** default config-scope to local ([a1a4b26](https://github.com/Claire-s-Monster/ci-framework/commit/a1a4b26e17c4785d0388d39dd3ed794d5a40833f)), closes [#348](https://github.com/Claire-s-Monster/ci-framework/issues/348)

## [3.0.0](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.9...v3.0.0) (2026-09-23)


### ⚠ BREAKING CHANGES

* **ci:** self-healing.yml drops the workflow_call inputs `healing-level`, `auto-fix`, `rollback-on-failure` and the output `fixes-applied`. See below.

### Features

* **ci:** expose overridable pixi-version input and explain lock-schema failures ([a149eb6](https://github.com/Claire-s-Monster/ci-framework/commit/a149eb665db88eeb34e2dba2c8c696a6ec8741fb))
* **ci:** expose overridable pixi-version input and explain lock-schema failures ([388d25a](https://github.com/Claire-s-Monster/ci-framework/commit/388d25a769ad47abb258ab8c8cf4d72d7ca1749d))
* **ci:** make the python-versions matrix test the interpreter it claims ([6586781](https://github.com/Claire-s-Monster/ci-framework/commit/658678117a5388bc4f019cd6a698b18953af3dc0))
* **ci:** make the python-versions matrix test the interpreter it claims ([8f5de89](https://github.com/Claire-s-Monster/ci-framework/commit/8f5de8916b04d373e7e85d573a2529c19cb77ad1))
* **lint:** shellcheck the bash embedded in composite actions ([41a399d](https://github.com/Claire-s-Monster/ci-framework/commit/41a399d9e4f07c7bf37e412fa88a234dafb6cce9))
* **lint:** shellcheck the bash embedded in composite actions ([12da1f2](https://github.com/Claire-s-Monster/ci-framework/commit/12da1f201e994a54f2972717fa60e96820707618)), closes [#261](https://github.com/Claire-s-Monster/ci-framework/issues/261) [#273](https://github.com/Claire-s-Monster/ci-framework/issues/273) [#274](https://github.com/Claire-s-Monster/ci-framework/issues/274)


### Bug Fixes

* **actions:** align fallback attribute names and guard attribute parity ([#291](https://github.com/Claire-s-Monster/ci-framework/issues/291)) ([334e19e](https://github.com/Claire-s-Monster/ci-framework/commit/334e19e6209247ca19212200ecdf0bcd43a417fa))
* **actions:** reject git refs beginning with '-' before they reach git ([#291](https://github.com/Claire-s-Monster/ci-framework/issues/291)) ([5fbff77](https://github.com/Claire-s-Monster/ci-framework/commit/5fbff77c9aee079805c68e4f6acbe2b909975785))
* **actions:** stop empty inputs from silently defeating their own defaults ([0458eb5](https://github.com/Claire-s-Monster/ci-framework/commit/0458eb5629a46dcb6b8d3400664198477e5f2a0f))
* **actions:** teach dependabot about actions/, and fix the pins it never saw ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([9a9ea2e](https://github.com/Claire-s-Monster/ci-framework/commit/9a9ea2e1e5a262bf3ab4ef3de0ee1e0a1c6b4f69))
* **actions:** thread every declared input into ChangeDetectionAction on both paths ([#291](https://github.com/Claire-s-Monster/ci-framework/issues/291)) ([c9abf44](https://github.com/Claire-s-Monster/ci-framework/commit/c9abf44309a362c8ce8717a12898266e75dd243d))
* **actions:** thread every declared input into ChangeDetectionAction on both paths ([#291](https://github.com/Claire-s-Monster/ci-framework/issues/291)) ([8f79bf2](https://github.com/Claire-s-Monster/ci-framework/commit/8f79bf229d9b19e4e4716862d860abfc11efd9c0))
* **actions:** wire up three inputs that were accepted and ignored ([37b1d55](https://github.com/Claire-s-Monster/ci-framework/commit/37b1d55627f5a26b9aca78b27d224ba43067e4cc))
* **actions:** wire up three inputs that were accepted and ignored ([51463f9](https://github.com/Claire-s-Monster/ci-framework/commit/51463f9d90b39adcc9d1cb6ceeb6bbb5b79fc507))
* **ci:** commit this framework's own pixi.lock and install from it ([975385c](https://github.com/Claire-s-Monster/ci-framework/commit/975385cad558bd6404b7225dcf813c2d564ec017))
* **ci:** commit this framework's own pixi.lock and install from it ([8c2ba84](https://github.com/Claire-s-Monster/ci-framework/commit/8c2ba84c62075b86501f42298d01f7a3327fe1aa))
* **ci:** declare shellcheck so local linting matches CI, and fix what it finds ([f4afb99](https://github.com/Claire-s-Monster/ci-framework/commit/f4afb997d7c61692530367904b3f7aaa61e81afa))
* **ci:** drop the unused setup-python step from the pixi matrix jobs ([a3dc00b](https://github.com/Claire-s-Monster/ci-framework/commit/a3dc00b816e82aee023519e8a4eddaf4944ed13e))
* **ci:** drop the unused setup-python step from the pixi matrix jobs ([9625d84](https://github.com/Claire-s-Monster/ci-framework/commit/9625d84e694f080a69b96edb2419fa2f43c9bc8d))
* **ci:** lint every workflow, and fix what that uncovers ([9ce47f8](https://github.com/Claire-s-Monster/ci-framework/commit/9ce47f89029bb229b39bf8d6fb12fc10cf437b72))
* **ci:** lint every workflow, and fix what that uncovers ([bd8b9e6](https://github.com/Claire-s-Monster/ci-framework/commit/bd8b9e6950dc9b673a34481d1e94f520a799fae3))
* **ci:** make the type-check gate propagate mypy's exit code ([b324618](https://github.com/Claire-s-Monster/ci-framework/commit/b32461804e7ac0339813acfd3a469c09b998274f))
* **ci:** make the type-check gate propagate mypy's exit code ([b533264](https://github.com/Claire-s-Monster/ci-framework/commit/b5332640ff3b8f10a295044fd072625985cef07e)), closes [#278](https://github.com/Claire-s-Monster/ci-framework/issues/278)
* **ci:** pin setup-codeql-matrix action ref to release tag instead of [@main](https://github.com/main) ([5b55245](https://github.com/Claire-s-Monster/ci-framework/commit/5b5524556fcbd253e7745bd912d7da77d0d0ae41))
* **ci:** run the pre-commit hooks that were configured but never fired ([31a20a7](https://github.com/Claire-s-Monster/ci-framework/commit/31a20a7a44961b7799798f49987c54de8c221a2a))
* **ci:** run the pre-commit hooks that were configured but never fired ([5589888](https://github.com/Claire-s-Monster/ci-framework/commit/5589888e7bd61766669659dd71f28332d5c1a82a))
* **ci:** satisfy ruff format gate and move workflow expressions out of run bodies ([9f12b4c](https://github.com/Claire-s-Monster/ci-framework/commit/9f12b4c6ab1e4f8fb751a147cfe50056fa293dac))
* **ci:** scope PYTHONNOUSERSITE=1 to the pytest step, not pixi activation ([9c5887c](https://github.com/Claire-s-Monster/ci-framework/commit/9c5887c89229147d62a3fb1e687df78557dfe2b6))
* **config:** point ruff and mypy at the 3.11 floor the project declares ([d95851a](https://github.com/Claire-s-Monster/ci-framework/commit/d95851ac4d041d3bf707aa6ddc58e60d646d8cd3))
* **config:** point ruff and mypy at the 3.11 floor the project declares ([7a0aa02](https://github.com/Claire-s-Monster/ci-framework/commit/7a0aa02fef57d00c6e816fcbce2c1fd5040e3e1a))
* **docs:** reconcile Python 3.10 references with the 3.11 floor, and guard the docs corpus ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([7e35bf5](https://github.com/Claire-s-Monster/ci-framework/commit/7e35bf5c110c200061f955c2cef57e4c99672343))
* **docs:** reconcile Python 3.10 references with the 3.11 floor, and guard the docs corpus ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([77380ef](https://github.com/Claire-s-Monster/ci-framework/commit/77380effe98c397192ec4799eba2c7a3fec316eb))
* **lint:** catch a swallow that a trailing `;` was hiding ([cdaa8cd](https://github.com/Claire-s-Monster/ci-framework/commit/cdaa8cdb81680bfdf3cb09247d627fdc777c9442)), closes [#278](https://github.com/Claire-s-Monster/ci-framework/issues/278)
* **lint:** do not mistake a mention of the anti-pattern for the anti-pattern ([60673df](https://github.com/Claire-s-Monster/ci-framework/commit/60673df7c3184797c390558c6172206625012bd9)), closes [#278](https://github.com/Claire-s-Monster/ci-framework/issues/278)
* **lint:** fail loudly when shellcheck does not run, and fix SC2002 ([9d16406](https://github.com/Claire-s-Monster/ci-framework/commit/9d16406f7bbd28058210328e8b31f4c772520d6e)), closes [#261](https://github.com/Claire-s-Monster/ci-framework/issues/261)
* **lint:** lint every workflow by discovery, not a six-file list ([c6d12b5](https://github.com/Claire-s-Monster/ci-framework/commit/c6d12b5526297f863a7c2b837f256127b858e2af))
* **lint:** lint every workflow by discovery, not a six-file list ([40bdb7b](https://github.com/Claire-s-Monster/ci-framework/commit/40bdb7b97a00dc3a761d060e7ed2dc2f2b0d5673)), closes [#279](https://github.com/Claire-s-Monster/ci-framework/issues/279)
* **lint:** run the gate against the pinned shellcheck, not any PATH build ([9b229f9](https://github.com/Claire-s-Monster/ci-framework/commit/9b229f9f4d8ed993c5411963b9df4138be9d53db)), closes [#261](https://github.com/Claire-s-Monster/ci-framework/issues/261)
* **lint:** widen yaml-lint to the action trees and wire it into CI ([f2abf68](https://github.com/Claire-s-Monster/ci-framework/commit/f2abf687d25de8c77615ec09a21a970f18539c0b))
* **lint:** widen yaml-lint to the action trees and wire it into CI ([0740e05](https://github.com/Claire-s-Monster/ci-framework/commit/0740e05307d166281356696688212d5382054675))
* **migration:** stop silently rewriting the consumer's python floor ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([88cfa5e](https://github.com/Claire-s-Monster/ci-framework/commit/88cfa5eaba60266b89d1bba3699f60aa8b610dcd))
* **pixi:** delegate every bare task to an env that provides its tool ([e353192](https://github.com/Claire-s-Monster/ci-framework/commit/e35319246dbfbfac0f95226b39d81d3c1a17837b))
* **pixi:** delegate every bare task to an env that provides its tool ([acdbd66](https://github.com/Claire-s-Monster/ci-framework/commit/acdbd66d006e32c421178fe06b6211d02d102e41))
* **pixi:** delete the dead ci-* task tier instead of repairing it ([#294](https://github.com/Claire-s-Monster/ci-framework/issues/294)) ([4a2cf69](https://github.com/Claire-s-Monster/ci-framework/commit/4a2cf69e58254a14a138cd22190838a2e4743935))
* **pixi:** delete the dead ci-* task tier instead of repairing it ([#294](https://github.com/Claire-s-Monster/ci-framework/issues/294)) ([35c3106](https://github.com/Claire-s-Monster/ci-framework/commit/35c31069f8847ce7db872f33e93df26531b7bb1b))
* **pixi:** move to [tool.pixi.workspace], and keep reading consumers' legacy [tool.pixi.project] ([0c2c655](https://github.com/Claire-s-Monster/ci-framework/commit/0c2c6550a1185339a1a1318d84441edab0875363))
* **pixi:** move to [tool.pixi.workspace], and keep reading consumers' legacy [tool.pixi.project] ([a9c86b3](https://github.com/Claire-s-Monster/ci-framework/commit/a9c86b3f8ffa47acc0a717024c6f5786b888e431))
* **python:** declare the 3.11 floor and make every tomllib import bare ([f162696](https://github.com/Claire-s-Monster/ci-framework/commit/f1626962d545b977ceb0cf86973db4b4ede852b9))
* **python:** declare the 3.11 floor and make every tomllib import bare ([f8eea08](https://github.com/Claire-s-Monster/ci-framework/commit/f8eea08319bf6aca2729e64af6bc6e423015628c)), closes [#281](https://github.com/Claire-s-Monster/ci-framework/issues/281)
* **python:** drop 3.10 from shipped config and CI matrix defaults ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286), PR-A of 3) ([44648f1](https://github.com/Claire-s-Monster/ci-framework/commit/44648f1fd21705156e5c60aa6bff95f20f88fc2f))
* **python:** drop 3.10 from shipped config and CI matrix defaults ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([6000918](https://github.com/Claire-s-Monster/ci-framework/commit/6000918d831cd2d517eb2f6cc5f5abc7b36ccf09))
* **quality:** make format-check env-self-contained and add it to the quality gate ([47fc4e6](https://github.com/Claire-s-Monster/ci-framework/commit/47fc4e67ecf8a2980f66c533c4b1aed69b9d546f))
* **quality:** make format-check env-self-contained and add it to the quality gate ([488e374](https://github.com/Claire-s-Monster/ci-framework/commit/488e3748692d3fedc1bd158106775c68eee1ff09))
* **quality:** point the mandatory gate at the full ruff ruleset ([08649cd](https://github.com/Claire-s-Monster/ci-framework/commit/08649cd7a74509a11a3d70ff4e2d28a75edaaf48))
* **quality:** point the mandatory gate at the full ruff ruleset ([17bc0c1](https://github.com/Claire-s-Monster/ci-framework/commit/17bc0c138718579575da3e8fcd042f1466916b3a)), closes [#271](https://github.com/Claire-s-Monster/ci-framework/issues/271)
* **quality:** run ruff from the pixi quality env instead of a second pinned rev ([873665a](https://github.com/Claire-s-Monster/ci-framework/commit/873665a6abaac31d1958ba4edd63200b871c8794))
* **quality:** run ruff from the pixi quality env instead of a second pinned rev ([bc22560](https://github.com/Claire-s-Monster/ci-framework/commit/bc2256075d4bca5b9dc54437f1644652fdc62e84))
* **review:** restore tiered matrix exclude, and guard workflows/ and scripts/ ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([711c58a](https://github.com/Claire-s-Monster/ci-framework/commit/711c58a5e28234c05ea72bbc16ab943830afe6de))
* **security:** close the last two heredoc injection sites ([87aefb0](https://github.com/Claire-s-Monster/ci-framework/commit/87aefb04d8e0dc63e45e8f326c69799f73678f27))
* **security:** close the last two heredoc injection sites ([cc114f0](https://github.com/Claire-s-Monster/ci-framework/commit/cc114f077117078e6c6670652c2e8c08b51f544a))
* **security:** close the SARIF sites the guard could not see ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([c439eb6](https://github.com/Claire-s-Monster/ci-framework/commit/c439eb679ad9fb770d0560638d6f4d4c8f67ca05))
* **security:** close the SARIF sites the guard could not see ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([c117b21](https://github.com/Claire-s-Monster/ci-framework/commit/c117b211f6b4ee7dc960cb35590ea3f70b37486a))
* **security:** keep GPG keys and bot tokens off the shell command line ([b93d5ed](https://github.com/Claire-s-Monster/ci-framework/commit/b93d5edf9614fa0f33c3b2a98ef4c1dd4310f8b3))
* **security:** keep GPG keys and bot tokens off the shell command line ([eb8aadd](https://github.com/Claire-s-Monster/ci-framework/commit/eb8aadd7c1fb32ab516af908d3770e41a3365881))
* **security:** let the two unauthorized SARIF uploads authenticate ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([894543b](https://github.com/Claire-s-Monster/ci-framework/commit/894543b63fed5fe4ab1f9b4ec768b89fb7a02986))
* **security:** let the two unauthorized SARIF uploads authenticate ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([d25aeb6](https://github.com/Claire-s-Monster/ci-framework/commit/d25aeb6eadc6f95396b0e61022dfa8644594f520))
* **security:** make detect-secrets run, and actually gate on what it finds ([#288](https://github.com/Claire-s-Monster/ci-framework/issues/288)) ([f356e02](https://github.com/Claire-s-Monster/ci-framework/commit/f356e020ce162a90e0f8dc25cc74df8baa25c8ed))
* **security:** make detect-secrets run, and actually gate on what it finds ([#288](https://github.com/Claire-s-Monster/ci-framework/issues/288)) ([c9d83cd](https://github.com/Claire-s-Monster/ci-framework/commit/c9d83cd25a9701028c595e28466e62f1efa8bf3c))
* **security:** make pip-audit and Bandit gate CI, and fix what they found ([#301](https://github.com/Claire-s-Monster/ci-framework/issues/301)) ([ab5359d](https://github.com/Claire-s-Monster/ci-framework/commit/ab5359d4f14ab70b67e6f5160b6225b593b4859f))
* **security:** make pip-audit and Bandit gate CI, and fix what they found ([#301](https://github.com/Claire-s-Monster/ci-framework/issues/301)) ([1c32774](https://github.com/Claire-s-Monster/ci-framework/commit/1c327740b6a957b5bba1483d843047adbab2731e))
* **security:** resync .secrets.baseline after the line shift this PR caused ([#301](https://github.com/Claire-s-Monster/ci-framework/issues/301)) ([68e768a](https://github.com/Claire-s-Monster/ci-framework/commit/68e768a2226117d6a79ab959c971a0e725280824))
* **security:** revert the CodeQL split - it reintroduced [#222](https://github.com/Claire-s-Monster/ci-framework/issues/222) ([#304](https://github.com/Claire-s-Monster/ci-framework/issues/304)) ([c86ab54](https://github.com/Claire-s-Monster/ci-framework/commit/c86ab54ca0ebfea1003a07edd45835fcdd0c76ca))
* **security:** stop splicing shell variables into action Python source ([6864e69](https://github.com/Claire-s-Monster/ci-framework/commit/6864e695a9ac425d4f57b791d0d640ec09eb6378))
* **security:** walk every workflow, and gate on the right invariant ([#304](https://github.com/Claire-s-Monster/ci-framework/issues/304)) ([a440a2c](https://github.com/Claire-s-Monster/ci-framework/commit/a440a2c39043505fe2e38a856d5e6ac6f677e5da))
* **security:** walk every workflow, and gate on the right invariant ([#304](https://github.com/Claire-s-Monster/ci-framework/issues/304)) ([cdbe1d5](https://github.com/Claire-s-Monster/ci-framework/commit/cdbe1d55e087323ea2f3083c4e3d1f8222c90920))
* **self-healing:** pin the local action ref so external consumers can resolve it ([ded156c](https://github.com/Claire-s-Monster/ci-framework/commit/ded156cc0c5f0e1676548c3f263ce1adc5edf4f3))
* **self-healing:** pin the local action ref so external consumers can resolve it ([879dc75](https://github.com/Claire-s-Monster/ci-framework/commit/879dc75e681efa661dfb61ec0eeecc52edd92838))
* **templates:** drop the docker-cross-platform action that never existed ([968e846](https://github.com/Claire-s-Monster/ci-framework/commit/968e8468f2345e60ff3f29b532081f20f81cd2b5))
* **templates:** drop the docker-cross-platform action that never existed ([df36d5b](https://github.com/Claire-s-Monster/ci-framework/commit/df36d5b0a026b43916c02f344abfbb9eccb2371f))
* **templates:** make every tool-invoking pixi task env-self-contained ([2f7906a](https://github.com/Claire-s-Monster/ci-framework/commit/2f7906ab37fb215bdf55cbf1e09e71acdd10e2e6))
* **templates:** make every tool-invoking pixi task env-self-contained ([a879897](https://github.com/Claire-s-Monster/ci-framework/commit/a879897750f3411a872e78c8065b9f55f5d688b8))
* **tests:** catch a compatibility-table row being deleted, not just mis-marked ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([d9716e3](https://github.com/Claire-s-Monster/ci-framework/commit/d9716e3572ac94f1c8d1bd4f35ad8f099d8c288d))
* **tests:** reconcile the compatibility matrix with the declared floor ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286), PR-B of 3) ([775d0fa](https://github.com/Claire-s-Monster/ci-framework/commit/775d0fa7da8c5aad1ebaa77840582c79a505fdaa))
* **tests:** reconcile the compatibility matrix with the declared floor ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([179d602](https://github.com/Claire-s-Monster/ci-framework/commit/179d602f2297361891f571385b10f0bc52330384))
* **tests:** report every sub-floor declaration, not just the first ([#286](https://github.com/Claire-s-Monster/ci-framework/issues/286)) ([4ecc9ff](https://github.com/Claire-s-Monster/ci-framework/commit/4ecc9ff4d0d138f9e164adf0c99ff9f94f9d24be))


### Documentation

* **security:** document fail-on-sast as a permanent opt-in gate ([#305](https://github.com/Claire-s-Monster/ci-framework/issues/305)) ([9c50862](https://github.com/Claire-s-Monster/ci-framework/commit/9c508624974acea909a524e42f1ba7e83809cc0e))
* **security:** document fail-on-sast as a permanent opt-in gate ([#305](https://github.com/Claire-s-Monster/ci-framework/issues/305)) ([8192a85](https://github.com/Claire-s-Monster/ci-framework/commit/8192a85f2f8f40e62d5aaca9ae7ee428e8fb7c96))
* **security:** document the caller permissions the action cannot grant itself ([#306](https://github.com/Claire-s-Monster/ci-framework/issues/306)) ([d2338bb](https://github.com/Claire-s-Monster/ci-framework/commit/d2338bbbf3d9ea29ce50ec0d8bec4b345a3abb5d))
* **test:** record the pixi coupling and the flat-scan decision ([2291fa1](https://github.com/Claire-s-Monster/ci-framework/commit/2291fa162b0cecb11230ea28d77af29f6c3ed538))

## [2.9.9](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.8...v2.9.9) (2026-07-29)


### Bug Fixes

* **ci:** bump pinned pixi CLI version to v0.74.0 (schema v7 support) ([e1c4612](https://github.com/Claire-s-Monster/ci-framework/commit/e1c4612b9f8cd445fd81255d3e5f097eaf457e4c))
* **ci:** bump pinned pixi CLI version to v0.74.0 (schema v7 support) ([a7a5a10](https://github.com/Claire-s-Monster/ci-framework/commit/a7a5a10cf4022448e528c63c48d55cb3dda39210))
* **ci:** key dependabot ai-analysis skip off PR author, not github.actor ([af1eb10](https://github.com/Claire-s-Monster/ci-framework/commit/af1eb10485591a355cd1455d83e26344692ec750))
* **ci:** key dependabot ai-analysis skip off PR author, not github.actor ([26c85ae](https://github.com/Claire-s-Monster/ci-framework/commit/26c85ae514b9efbe810ea008a5fbdcd28ad39447))
* **ci:** skip Gemini AI review on dependabot pull_request runs ([da9faa6](https://github.com/Claire-s-Monster/ci-framework/commit/da9faa62d56cc84cbf55e61d9889c79dec7c4ac8))
* **ci:** skip Gemini AI review on dependabot pull_request runs ([d69692d](https://github.com/Claire-s-Monster/ci-framework/commit/d69692d291038d8099c07435154592e9d1ef852f))

## [2.9.8](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.7...v2.9.8) (2026-07-18)


### Bug Fixes

* **ci:** add codeql-languages allowlist + harden c-cpp CodeQL leg ([#227](https://github.com/Claire-s-Monster/ci-framework/issues/227)) ([d8cb23d](https://github.com/Claire-s-Monster/ci-framework/commit/d8cb23d083f894d4e054321881414d8514f9146b))
* **ci:** add codeql-languages allowlist + harden c-cpp leg ([#227](https://github.com/Claire-s-Monster/ci-framework/issues/227)) ([503b8b7](https://github.com/Claire-s-Monster/ci-framework/commit/503b8b7aac6b122b2451c85074257b321f026c3b))
* **ci:** avoid expression injection in codeql-matrix step ([#227](https://github.com/Claire-s-Monster/ci-framework/issues/227)) ([5dae189](https://github.com/Claire-s-Monster/ci-framework/commit/5dae189593e176e2746adb8e061df9f37defc1e3))
* **ci:** validate codeql-languages against strict allowlist ([#227](https://github.com/Claire-s-Monster/ci-framework/issues/227)) ([fac4555](https://github.com/Claire-s-Monster/ci-framework/commit/fac455573498c2f8ec30bc7df6424afb7b1432dd))

## [2.9.7](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.6...v2.9.7) (2026-07-15)


### Bug Fixes

* **ci:** grant gemini-ai-analysis.yml the permissions its reusable workflow needs ([03bb471](https://github.com/Claire-s-Monster/ci-framework/commit/03bb471487b5f3d4dfbe5e473548575997d0d438))
* **ci:** grant gemini-ai-analysis.yml the permissions its reusable workflow needs ([8aa9b25](https://github.com/Claire-s-Monster/ci-framework/commit/8aa9b252afb5bdb0e6931db1f94ebc54d8a13a4c))
* **ci:** keep CodeQL analyze non-blocking with continue-on-error ([#222](https://github.com/Claire-s-Monster/ci-framework/issues/222)) ([4f55357](https://github.com/Claire-s-Monster/ci-framework/commit/4f55357cad9bc3b99be495a4aa1341d651eca106))
* **ci:** set native CodeQL check conclusion via analyze upload:true ([#222](https://github.com/Claire-s-Monster/ci-framework/issues/222)) ([4929453](https://github.com/Claire-s-Monster/ci-framework/commit/49294534b08fe1c837a925a4740a31a7bf4be668))
* **ci:** set native CodeQL check conclusion via analyze upload:true ([#222](https://github.com/Claire-s-Monster/ci-framework/issues/222)) ([7e79d25](https://github.com/Claire-s-Monster/ci-framework/commit/7e79d258147b3bb30f8255a2f9d074fe45cad0aa))

## [2.9.6](https://github.com/Claire-s-Monster/ci-framework/compare/v2.9.5...v2.9.6) (2026-07-15)


### Bug Fixes

* **ci:** drop emoji prefix from Security Scan job name ([83131a3](https://github.com/Claire-s-Monster/ci-framework/commit/83131a3f63400f2be691bbfa5e04f411dd84669b))
* **ci:** drop emoji prefix from Security Scan job name ([563fc34](https://github.com/Claire-s-Monster/ci-framework/commit/563fc340900f72af12614c04ceb485250e552d74))
* **ci:** gate reusable-ci.yml CodeQL behind `codeql` input to prevent duplicate codeql-python upload ([#215](https://github.com/Claire-s-Monster/ci-framework/issues/215)) ([#216](https://github.com/Claire-s-Monster/ci-framework/issues/216)) ([64aedd1](https://github.com/Claire-s-Monster/ci-framework/commit/64aedd129770345e786ff64b502dc92285ad2e38))

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
