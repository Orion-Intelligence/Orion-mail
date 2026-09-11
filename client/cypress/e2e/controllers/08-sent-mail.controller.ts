export function openComposeForSend() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1);
}

export function fillSendMail(
  receiver: string,
  subject: string,
  message: string
) {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="receiver-input"]')
        .should('be.visible')
        .clear()
        .type(receiver);

      cy.get('[data-testid="subject-input"]')
        .should('be.visible')
        .clear()
        .type(subject);

      cy.get(
        '[data-testid="rich-text-editor"], [data-testid="message-input"]'
      )
        .should('be.visible')
        .then(($editor) => {
          if ($editor.attr('data-testid') === 'rich-text-editor') {
            cy.wrap($editor)
              .click()
              .type(message);
          } else {
            cy.wrap($editor)
              .clear()
              .type(message);
          }
        });
    });
}

export function sendMail() {
  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('sendMailRequest');

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="send-button"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();
    });

  void cy.wait('@sendMailRequest')
    .its('response.statusCode')
    .should('eq', 200);
}

export function openSent() {
  void cy.intercept({
    method: 'GET',
    pathname: '**/messages/sent',
  }).as('loadSent');

  void cy.get('[data-testid="sent-section"]')
    .filter(':visible')
    .first()
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/sent');

  void cy.wait('@loadSent')
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertMessageExistsInSent(subject: string) {
  void cy.get('[data-testid="message-list"]')
    .filter(':visible')
    .should('have.length', 1)
    .within(() => {
      cy.contains(
        '[data-testid="message-subject"]',
        subject
      ).should('be.visible');
    });
}

export function openSentMessage(subject: string) {
  void cy.get('[data-testid="message-list"]')
    .filter(':visible')
    .should('have.length', 1)
    .within(() => {
      cy.contains(
        '[data-testid="message-subject"]',
        subject
      )
        .should('be.visible')
        .click();
    });
}

export function assertSentMessageContent(
  receiver: string,
  subject: string,
  message: string
) {
  void cy.get('body')
    .should('contain.text', receiver);

  void cy.get('body')
    .should('contain.text', subject);

  void cy.get('body')
    .should('contain.text', message);
}
