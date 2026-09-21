describe('Sign-in maintenance page', () => {
    for (const width of [320, 1280]) {
        it(`shows the maintenance design on a sign-in outage at ${width}px`, () => {
            cy.viewport(width, 800);
            cy.intercept('GET', '**/auth/me', { statusCode: 503, body: { detail: 'Service Not Ready' } });
            cy.intercept('GET', '**/health', { statusCode: 503 });
            cy.visit('/messenger');
            cy.location('pathname').should('eq', '/maintenance.html');
            cy.title().should('eq', 'Orion Mail Maintenance');
            cy.contains('h1', 'Orion is temporarily unavailable').should('be.visible');
            cy.get('.logo').should('be.visible').and(($image) => {
                expect(($image[0] as HTMLImageElement).naturalWidth).to.be.greaterThan(0);
            });
            cy.get('body').should('have.css', 'background-image').and('include', 'linear-gradient');
            cy.get('main').then(($main) => {
                expect($main[0].getBoundingClientRect().right).to.be.at.most(width);
            });
            cy.contains('a', 'Try again').should('have.attr', 'href', '/inbox');
            cy.screenshot(`maintenance-${width}`, { capture: 'viewport' });
        });
    }
});
