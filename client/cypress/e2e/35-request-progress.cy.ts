const progressUser = {
    id: 'progress-user', username: 'reader', full_name: 'Reader',
    mailbox_configured: true, mailbox_address: 'reader@example.test',
    preferences: { theme: 'dark' },
};
const progressMessage = {
    id: 'progress-message', sender_address: 'sender@example.test',
    receiver_address: 'reader@example.test', to_addresses: ['reader@example.test'],
    cc_addresses: [], subject: 'Progress check', body: 'Test message',
    attachments: [], label_ids: [], is_read: true, is_starred: false, is_important: false,
    direction: 'incoming', folder: 'inbox', thread_id: 'progress-message',
    has_original_source: false, created_at: '2026-09-24T00:00:00Z',
};
const progressCounts = { inbox: 1, sent: 1, drafts: 0, spam: 0, trash: 0, archive: 0, unread: { inbox: 0 } };
const progressBar = '[data-testid="loading-progress"]';

describe('Shared request progress', { defaultCommandTimeout: 5000 }, () => {
    beforeEach(() => {
        cy.intercept('GET', '**/auth/me', progressUser);
        cy.intercept('GET', '**/mailboxes/me', { mailbox_address: 'reader@example.test' });
        cy.intercept('GET', '**/mailboxes/me/e2e-key', { configured: false, mailbox_address: 'reader@example.test' });
        cy.intercept('GET', '**/labels', []);
        cy.intercept('GET', '**/messages/folder-counts', progressCounts);
        cy.intercept('GET', '**/messages/storage-status', { storage_exceeded: false });
        cy.intercept('GET', '**/messages/inbox*', [progressMessage]);
        cy.intercept('GET', '**/messages/sent', { delay: 500, body: [progressMessage] });
        cy.intercept('GET', '**/messages/progress-message', { delay: 150, body: progressMessage });
        cy.intercept('GET', '**/messages/progress-message/thread', []);
        cy.visit('/inbox');
        cy.get('[data-testid="inbox-message-item"]').should('be.visible');
        cy.get(progressBar).should('not.be.visible');
    });

    for (const width of [1280, 390]) {
        it(`places progress directly below the Inbox toolbar without shifting rows at ${width}px`, () => {
            cy.viewport(width, 800);
            let releaseInbox: () => void;
            cy.intercept('GET', '**/messages/inbox*', (request) => new Promise<void>((resolve) => {
                releaseInbox = () => {
                    request.reply([progressMessage]);
                    resolve();
                };
            }));
            cy.get('[data-testid="inbox-message-item"]').then(($row) => {
                const originalTop = $row[0].getBoundingClientRect().top;
                cy.get('[data-testid="refresh-inbox-button"]').click();
                cy.get('[data-testid="inbox-toolbar"]').then(($toolbar) => {
                    const toolbar = $toolbar[0].getBoundingClientRect();
                    cy.wrap($toolbar).next('app-request-progress').find(progressBar)
                        .should('be.visible').and(($bar) => {
                            const bar = $bar[0].getBoundingClientRect();
                            expect(bar.top).to.be.closeTo(toolbar.bottom, 0.5);
                            expect(bar.left).to.be.closeTo(toolbar.left, 0.5);
                            expect(bar.width).to.be.closeTo(toolbar.width, 0.5);
                        });
                });
                cy.get(progressBar).should('have.length', 1);
                cy.get('[data-testid="inbox-message-item"]').should(($current) => {
                    expect($current[0].getBoundingClientRect().top).to.eq(originalTop);
                });
                cy.then(() => releaseInbox());
                cy.get(progressBar).should('not.be.visible');
                cy.get('[data-testid="inbox-message-item"]').should(($current) => {
                    expect($current[0].getBoundingClientRect().top).to.eq(originalTop);
                });
            });
        });
    }

    it('starts during the session check, before the destination page loads', () => {
        let releaseSession: () => void;
        cy.intercept('GET', '**/auth/me', (request) => new Promise<void>((resolve) => {
            releaseSession = () => {
                request.reply(progressUser);
                resolve();
            };
        }));
        cy.get('a[data-testid="sent-section"]').click();
        cy.get(progressBar).should('be.visible').and('have.attr', 'role', 'progressbar');
        cy.location('pathname').should('eq', '/inbox');
        cy.then(() => releaseSession());
        cy.get('app-sent').should('exist');
        cy.get(progressBar).should('be.visible').and('have.length', 1);
        cy.get('[data-testid="sent-toolbar"]').then(($toolbar) => {
            cy.wrap($toolbar).next('app-request-progress').find(progressBar).should(($bar) => {
                expect($bar[0].getBoundingClientRect().top).to.be.closeTo($toolbar[0].getBoundingClientRect().bottom, 1);
            });
        });
        cy.get('app-sent [data-testid="message-row"]').should('be.visible');
        cy.get(progressBar).should('not.be.visible');
    });

    it('stays visible until overlapping requests have all finished', () => {
        let threadFinished = false;
        cy.intercept('GET', '**/messages/progress-message/thread', (request) => {
            request.on('after:response', () => { threadFinished = true; });
            request.reply({ delay: 1000, body: [] });
        }).as('thread');
        cy.get('[data-testid="message-subject"]').click();
        cy.get('[data-testid="message-card"]').should('be.visible');
        cy.get(progressBar).should('be.visible').and('have.length', 1).then(() => {
            expect(threadFinished).to.eq(false);
        });
        cy.wait('@thread');
        cy.get(progressBar).should('not.be.visible');
    });

    it('clears progress after a failed request', () => {
        cy.intercept('GET', '**/messages/sent', {
            delay: 500, statusCode: 500, body: { detail: 'Fixture failure' },
        });
        cy.get('a[data-testid="sent-section"]').click();
        cy.get(progressBar).should('be.visible');
        cy.get('app-sent [role="alert"]').should('contain.text', 'Could not load sent emails');
        cy.get(progressBar).should('not.be.visible');
    });

    it('clears cancelled requests when leaving a message', () => {
        cy.intercept('GET', '**/messages/progress-message/thread', { delay: 3000, body: [] });
        cy.get('[data-testid="message-subject"]').click();
        cy.get('[data-testid="message-card"]').should('be.visible');
        cy.get(progressBar).should('be.visible');
        cy.get('[data-testid="back-button"]').click();
        cy.get('[data-testid="inbox-message-item"]').should('be.visible');
        cy.get(progressBar, { timeout: 1000 }).should('not.be.visible');
    });

    it('does not start another bar for the background count refresh', () => {
        let countsFinished = false;
        cy.intercept('GET', '**/messages/folder-counts', (request) => {
            request.on('after:response', () => { countsFinished = true; });
            request.reply({ delay: 1200, body: progressCounts });
        }).as('counts');
        cy.intercept('GET', '**/messages/inbox*', { delay: 300, body: [progressMessage] }).as('inbox');
        cy.get('[data-testid="refresh-inbox-button"]').click();
        cy.get(progressBar).should('be.visible');
        cy.wait('@inbox');
        cy.get(progressBar, { timeout: 700 }).should('not.be.visible').then(() => {
            expect(countsFinished).to.eq(false);
        });
        cy.wait('@counts');
        cy.get(progressBar).should('not.be.visible');
    });
});
