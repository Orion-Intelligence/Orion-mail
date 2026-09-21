import { assertMessengerChatVisible, openAllUsersTab, openChatsTab, openFirstMessengerUser, openMessengerFromNavbar, searchMessengerUser, sendMessengerMessage} from './controllers/33-message-messanger.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Messenger', () => {

    it('starts a messenger chat from all users search', () => {
        const message = `Hello ${Date.now()}`;

        loginAsTestUser('test2');

        cy.visit('/inbox');

        cy.get('[data-testid="messenger-section"]')
            .should('be.visible');

        openMessengerFromNavbar();

        openAllUsersTab();

        searchMessengerUser('test1');

        openFirstMessengerUser('test1');

        sendMessengerMessage(message);

        openChatsTab();

        assertMessengerChatVisible(message);
    });

});