import { loginAsTestUser } from './test-mail.controller';

export function removeEncryptionKey(username: string) {
    loginAsTestUser(username);

    void cy.request({ method: 'DELETE', url: '/api/mailboxes/me/e2e-key', headers: { 'X-Requested-With': 'XMLHttpRequest' }, failOnStatusCode: false });
}

export function setUpEncryptionKey(username: string) {
    removeEncryptionKey(username);

    void cy.visit('/inbox', {
        onBeforeLoad: (win) => {
            win.localStorage.setItem('orion_mail_e2e_tests', 'on');
        },
    });

    void cy.get('[data-testid="e2e-setup-passphrase"]')
        .should('be.visible')
        .type('cypress mail passphrase');

    void cy.get('[data-testid="e2e-setup-confirm"]')
        .type('cypress mail passphrase');

    void cy.get('[data-testid="e2e-dialog-submit"]')
        .click();

    void cy.get('[data-testid="e2e-recovery-code-value"]', { timeout: 60000 })
        .should('be.visible')
        .invoke('text')
        .should('match', /^\s*([A-Z2-9]{4}-){7}[A-Z2-9]{4}\s*$/);

    void cy.get('[data-testid="e2e-recovery-done"]')
        .should('be.disabled');

    void cy.get('[data-testid="e2e-recovery-saved"]')
        .check();

    void cy.get('[data-testid="e2e-recovery-done"]')
        .click();

    void cy.get('[data-testid="e2e-dialog-form"]')
        .should('not.exist');
}

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