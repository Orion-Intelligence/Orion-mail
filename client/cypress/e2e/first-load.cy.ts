describe("first page load", () => {
    it("boots the Orion Mail application shell and starts the Orion sign-in handshake", () => {
        cy.intercept("GET", "**/auth/me", { statusCode: 401, body: { detail: "Invalid or expired session" } }).as("currentUser");

        cy.visit("/", {
            onBeforeLoad(win) {
                cy.stub(win.location, "assign").as("signInRedirect");
            },
        });

        cy.wait("@currentUser").its("request.url").should("include", "/auth/me");
        cy.get("@signInRedirect").should("have.been.calledWithMatch", "/auth/login");
    });
});
