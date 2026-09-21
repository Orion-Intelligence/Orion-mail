import { assertMessengerChatVisible, openAllUsersTab, openChatsTab, openFirstMessengerUser, openMessengerFromNavbar, removeEncryptionKey, searchMessengerUser, sendMessengerMessage, setUpEncryptionKey } from './controllers/33-message-messanger.controller';

describe('Orion Mail - Messenger', () => {

    after(() => {
        removeEncryptionKey('test1');
        removeEncryptionKey('test2');
    });

    it('starts a messenger chat from all users search', () => {
        const message = `Hello ${Date.now()}`;

        setUpEncryptionKey('test1');
        setUpEncryptionKey('test2');

        cy.intercept('POST', '**/messenger-api/messages').as('chatSend');

        cy.get('[data-testid="messenger-section"]')
            .should('be.visible');

        openMessengerFromNavbar();

        openAllUsersTab();

        searchMessengerUser('test1');

        openFirstMessengerUser('test1');

        sendMessengerMessage(message);

        cy.wait('@chatSend').then(({ request, response }) => {
            expect(response?.statusCode).to.eq(200);
            expect(request.body.body).to.match(/^-----BEGIN PGP MESSAGE-----/);
            expect(request.body.body).not.to.contain(message);
        });

        openChatsTab();

        assertMessengerChatVisible(message);
    });

});