const user = { id: 'responsive-user', username: 'alex', full_name: 'Alex Example', mailbox_address: 'alex@example.test', fingerprint: 'test-fingerprint' };

function stubMailShell() {
    cy.intercept('GET', '**/auth/me', {
        id: 'layout-test', full_name: 'Layout Test', username: 'layout', email: 'layout@example.test',
        mailbox_configured: true, mailbox_address: 'layout@example.test', mail_domain: 'example.test',
        orion_account_url: 'https://example.test', preferences: { theme: 'dark' },
    });
    cy.intercept('GET', '**/labels*', []);
    cy.intercept('GET', '**/messages/storage-status', { body: { storage_exceeded: false } });
    cy.intercept('GET', '**/messages/folder-counts', { total: {}, unread: { inbox: 0 } });
    cy.intercept('GET', '**/mailboxes/me', { mailbox_address: 'layout@example.test' });
}

// Messenger responses are fixtures so this regression never sends real messages.
describe('Messenger responsive layout', () => {
    for (const width of [320, 390, 768, 1280]) {
        it(`opens and navigates a conversation at ${width}px`, () => {
            cy.viewport(width, 844);
            stubMailShell();
            cy.intercept('GET', '**/messenger-api/users*', [user]);
            cy.intercept('GET', '**/messenger-api/conversations', []);
            cy.intercept('GET', '**/messenger-api/conversations/*/messages', [
                { id: 'received', direction: 'received', body: 'Long message ' + 'a'.repeat(250), created_at: '2026-09-21T12:00:00Z' },
                { id: 'sent', direction: 'sent', body: 'Thanks, received.', created_at: '2026-09-21T12:01:00Z' },
            ]);
            cy.intercept('POST', '**/messenger-api/messages', {
                statusCode: 500, body: { detail: 'Test send failure' },
            });
            cy.visit('/messenger');
            cy.get('[data-testid="messenger-user-item"]').first().click();
            cy.get('[data-testid="messenger-chat-panel"]').should('be.visible');
            cy.get('[data-testid="messenger-message-bubble"]').should('have.length', 2);
            cy.get('.messenger-composer').then(($bar) => {
                expect($bar[0].getBoundingClientRect().height).to.be.at.most(58);
            });
            if (width === 390 || width === 1280) {
                cy.screenshot(`messenger-${width}-dark`, { capture: 'viewport' });
            }
            cy.get('[data-testid="messenger-message-input"]').should('be.visible').type('First line{enter}Second line{enter}Third line')
                .then(($input) => { expect($input[0].clientHeight).to.be.greaterThan(60); });
            cy.get('[data-testid="messenger-send-button"]').should('be.visible').click();
            cy.get('[data-testid="messenger-chat-panel"] [role="alert"]').should('be.visible').and('contain.text', 'Test send failure');
            cy.get('[data-testid="messenger-page"]').then(($page) => {
                expect($page[0].scrollWidth).to.be.at.most($page[0].clientWidth + 1);
            });
            cy.get('[data-testid="messenger-send-button"]').then(($button) => {
                const bounds = $button[0].getBoundingClientRect();
                expect(bounds.bottom).to.be.at.most(844);
                expect(bounds.right).to.be.at.most(width);
            });
            if (width <= 900) {
                cy.get('[data-testid="messenger-user-list"]').should('not.be.visible');
                cy.get('[data-testid="messenger-back-button"]').should('be.visible').click();
                cy.get('[data-testid="messenger-user-list"]').should('be.visible');
                cy.get('[data-testid="messenger-chat-panel"]').should('not.be.visible');
                cy.get('[data-testid="messenger-user-item"]').first().click();
                cy.get('[data-testid="messenger-message-input"]').should('be.visible');
            } else {
                cy.get('[data-testid="messenger-user-list"]').should('be.visible');
                cy.get('[data-testid="messenger-back-button"]').should('not.be.visible');
            }
        });
    }

    it('keeps chat rows, drafts and cached messages stable while switching', () => {
        cy.viewport(1280, 844);
        stubMailShell();
        const secondUser = { ...user, id: 'second-user', full_name: 'Sam Example' };
        const conversations = [user, secondUser].map((other_user) => ({
            id: other_user.id, other_user, last_message: `Hello from ${other_user.full_name}`,
            last_message_at: '2026-09-21T12:00:00Z', unread_count: 0,
        }));
        cy.intercept('GET', '**/messenger-api/users*', [user, secondUser]);
        let conversationRequests = 0;
        cy.intercept('GET', '**/messenger-api/conversations', (req) => {
            req.reply({ body: conversations, delay: conversationRequests++ === 0 ? 0 : 800 });
        });
        let messageRequests = 0;
        cy.intercept('GET', '**/messenger-api/conversations/*/messages', (req) => {
            messageRequests++;
            const isAlex = req.url.includes(user.id);
            req.reply({ delay: messageRequests > 1 ? 600 : 0, body: [{
                id: isAlex ? 'alex-message' : 'sam-message', direction: 'received',
                body: isAlex ? 'Message from Alex' : 'Message from Sam', created_at: '2026-09-21T12:00:00Z',
            }] });
        }).as('chatMessages');
        cy.visit('/messenger');
        cy.get('[data-testid="messenger-conversation-item"]').first().then(($row) => {
            const originalRow = $row[0];
            cy.wrap($row).click();
            cy.wait('@chatMessages');
            cy.contains('[data-testid="messenger-message-bubble"]', 'Message from Alex').should('be.visible');
            cy.get('[data-testid="messenger-message-input"]').type('Unsent draft');
            cy.get('[data-testid="messenger-conversation-item"]').first().click().then(() => {
                expect(messageRequests).to.eq(1);
                expect(originalRow.isConnected).to.eq(true);
            });
            cy.get('[data-testid="messenger-message-input"]').should('have.value', 'Unsent draft');
            cy.contains('Loading chats…').should('not.exist');
            cy.get('[data-testid="messenger-conversation-item"]').eq(1).click();
            cy.wait('@chatMessages');
            cy.contains('[data-testid="messenger-message-bubble"]', 'Message from Sam').should('be.visible');
            cy.get('[data-testid="messenger-conversation-item"]').first().click();
            cy.contains('[data-testid="messenger-message-bubble"]', 'Message from Alex').should('be.visible');
            cy.contains('Loading messages…').should('not.exist');
            cy.get('[data-testid="messenger-message-input"]').should('have.value', 'Unsent draft');
            cy.wait('@chatMessages');
            cy.get('[data-testid="messenger-conversation-item"]').first().then(($current) => {
                expect($current[0]).to.eq(originalRow);
            });
        });
    });

});
