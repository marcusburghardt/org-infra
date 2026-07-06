// SPDX-License-Identifier: Apache-2.0
// Renovate configuration for complytime org.
// Manages Go toolchain patch updates across Go repositories.
// Preset rules are defined in go-toolchain-patches.json.
module.exports = {
  platform: 'github',
  onboarding: false,
  requireConfig: 'optional',
  autodiscover: true,
  autodiscoverFilter: ['complytime/*'],
  globalExtends: [
    'github>complytime/org-infra:go-toolchain-patches',
  ],
};
