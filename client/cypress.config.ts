import { defineConfig } from "cypress";
import registerCodeCoverageTasks from "@cypress/code-coverage/task";
import fs from "node:fs";
import path from "node:path";

const isCi =
    process.env["CI"] === "true" ||
    process.env["GITHUB_ACTIONS"] === "true" ||
    process.env["GITLAB_CI"] === "true";
const coverageEnabled = isCi || process.env["ORION_COVERAGE"] === "true";

export default defineConfig({
    allowCypressEnv: false,
    video: false,
    screenshotsFolder: "cypress/error",
    screenshotOnRunFailure: true,
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
        takeScreenshots: false,
    },
    expose: {
        coverage: coverageEnabled,
    },
    e2e: {
        specPattern: "cypress/e2e/**/*.{cy,spec}.{ts,js}",
        supportFile: "cypress/support/e2e.ts",
        testIsolation: true,
        setupNodeEvents(on, config) {
            const takeScreenshots = config.env["takeScreenshots"];
            if (takeScreenshots === true || takeScreenshots === "true") {
                config.screenshotsFolder = "../docs/screenshots";
            }
            on("after:screenshot", (details) => {
                if (!details.testFailure) {
                    return;
                }
                const screenshotsFolder =
                    typeof config.screenshotsFolder === "string" ? config.screenshotsFolder : "cypress/error";
                const screenshotRoot = path.resolve(config.projectRoot, screenshotsFolder);
                const relativePath = path.relative(screenshotRoot, details.path);
                const targetPath = path.resolve(config.projectRoot, "cypress", "error", relativePath);

                if (details.path === targetPath) {
                    return;
                }

                fs.mkdirSync(path.dirname(targetPath), { recursive: true });
                fs.renameSync(details.path, targetPath);

                return { path: targetPath };
            });
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
