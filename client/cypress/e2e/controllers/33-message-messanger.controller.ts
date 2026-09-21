export function openMessengerFromNavbar() {
    void cy.get('[data-testid="messenger-section"]')
        .should('be.visible')
        .click();

    void cy.url()
        .should('include', '/messenger');

    void cy.get('[data-testid="messenger-page"]')
        .should('be.visible');
}

export function openAllUsersTab() {
    void cy.get('[data-testid="messenger-all-users-tab"]')
        .should('be.visible')
        .click();
}

export function searchMessengerUser(searchText: string) {
    void cy.get('[data-testid="messenger-search-input"]')
        .should('be.visible')
        .clear()
        .type(searchText);
}

export function openFirstMessengerUser(expectedText: string) {
    void cy.get('[data-testid="messenger-user-item"]')
        .should('have.length.greaterThan', 0)
        .first()
        .should('be.visible')
        .and('contain.text', expectedText)
        .click();

    void cy.get('[data-testid="messenger-chat-panel"]')
        .should('be.visible');
}

export function sendMessengerMessage(message: string) {
    void cy.get('[data-testid="messenger-message-input"]')
        .should('be.visible')
        .clear()
        .type(message);

    void cy.get('[data-testid="messenger-send-button"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();

    void cy.contains('[data-testid="messenger-message-bubble"]', message)
        .should('be.visible');
}

export function clearMessengerSearch() {
    void cy.get('[data-testid="messenger-search-input"]')
        .should('be.visible')
        .clear();
}

export function openChatsTab() {
    clearMessengerSearch();

    void cy.get('[data-testid="messenger-chats-tab"]')
        .should('be.visible')
        .click();
}

export function assertMessengerChatVisible(message: string) {
    void cy.contains('[data-testid="messenger-conversation-item"]', message)
        .should('be.visible');
}