import { defineConfig } from "cypress";
import registerCodeCoverageTasks from "@cypress/code-coverage/task";

const isCi =
    process.env["CI"] === "true" ||
    process.env["GITHUB_ACTIONS"] === "true" ||
    process.env["GITLAB_CI"] === "true";
const coverageEnabled = isCi || process.env["ORION_COVERAGE"] === "true";

export default defineConfig({
    allowCypressEnv: false,
    video: false,
    screenshotOnRunFailure: false,
    numTestsKeptInMemory: 0,
    watchForFileChanges: false,
    trashAssetsBeforeRuns: false,
    experimentalMemoryManagement: true,
    retries: 0,
    env: {
        coverage: coverageEnabled,
        language: "en",
        codeCoverage: {
            enabled: coverageEnabled,
        },
    },
    expose: {
        coverage: coverageEnabled,
    },
    e2e: {
        specPattern: "cypress/e2e/**/*.{cy,spec}.{ts,js}",
        supportFile: "cypress/support/e2e.ts",
        testIsolation: true,
        setupNodeEvents(on, config) {
            if (coverageEnabled) {
                registerCodeCoverageTasks(on, config);
            }
            on("before:browser:launch", (browser, launchOptions) => {
                if (browser.family === "chromium") {
                    launchOptions.args.push("--start-maximized");
                    launchOptions.args.push("--window-size=1920,1080");
                    launchOptions.args.push("--force-device-scale-factor=1");
                }
                return launchOptions;
            });
            on("task", {
                log(_) {
                    return null;
                },
                table(_) {
                    return null;
                },
            });
            return config;
        },
        baseUrl: process.env["ORION_E2E_BASE_URL"] || "http://127.0.0.1:4300",
      // baseUrl: process.env["ORION_E2E_BASE_URL"] || "http://mail.localhost:4300",
        viewportWidth: 1920,
        viewportHeight: 1080,
        defaultCommandTimeout: 60000,
        requestTimeout: 60000,
        responseTimeout: 60000,
        pageLoadTimeout: 60000,
        execTimeout: 60000,
        taskTimeout: 60000,
        waitForAnimations: true,
        animationDistanceThreshold: 5,
    },
    component: {
        devServer: {
            framework: "angular",
            bundler: "webpack",
        },
        specPattern: "cypress/**/*.cy.ts",
    },
});
