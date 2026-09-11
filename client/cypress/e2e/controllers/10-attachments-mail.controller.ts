export function openComposeForAttachment() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1);
}

export function fillAttachmentMail(
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

export function attachTestFile(
  fileName: string,
  fileContent: string
) {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="file-input"]')
        .selectFile(
          {
            contents: Cypress.Buffer.from(fileContent),
            fileName,
            mimeType: 'text/plain',
          },
          {
            force: true,
          }
        );

      cy.get('[data-testid="selected-attachment"]')
        .should('be.visible')
        .and('contain.text', fileName);
    });
}

export function sendAttachmentMail() {
  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('sendAttachmentMailRequest');

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="send-button"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();
    });

  void cy.wait('@sendAttachmentMailRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function openInboxMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    {
      timeout: 15000,
    }
  )
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]')
    .should('be.visible');
}

export function assertAttachmentExists(fileName: string) {
  void cy.get('[data-testid="attachments-section"]')
    .should('be.visible')
    .and('contain.text', fileName);

  void cy.get('[data-testid="download-attachment-button"]')
    .should('be.visible');
}
