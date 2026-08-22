describe("first page load", () => {
    it("boots the Orion Mail application shell and starts the Orion sign-in handshake", () => {
        cy.intercept("GET", "**/auth/me", { statusCode: 401, body: { detail: "Invalid or expired session" } }).as("currentUser");
        cy.intercept("GET", "**/auth/login*", { statusCode: 200, body: "orion-sso-stub" }).as("orionLogin");

        cy.visit("/");

        cy.wait("@currentUser").its("request.url").should("include", "/auth/me");
        cy.wait("@orionLogin").its("request.url").should("include", "/auth/login");
    });
});
