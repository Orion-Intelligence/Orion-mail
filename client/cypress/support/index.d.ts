export {};

declare global {
    namespace Cypress {
        interface Chainable {
            mount: typeof import("cypress/angular").mount;
        }
    }
}
