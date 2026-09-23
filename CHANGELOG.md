# Changelog

All notable changes to the CI Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
