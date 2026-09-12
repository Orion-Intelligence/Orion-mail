export function openCompose() {
  void cy.get('[data-testid="compose-button"]').should('be.visible').click();
  void cy.get('[data-testid="compose-form"]').filter(':visible').should('have.length', 1);
}

function visibleForm() {
  return cy.get('[data-testid="compose-form"]').filter(':visible');
}

export function applyListAndClearFormatting() {
  void visibleForm().within(() => {
    cy.get('[data-testid="formatting-toolbar"]').should('be.visible');

    cy.get('[data-testid="rich-text-editor"]')
      .should('be.visible')
      .click()
      .type('First item{enter}Second item');

    cy.get('[data-testid="bulleted-list-button"]').should('be.visible').click();
    cy.get('[data-testid="numbered-list-button"]').should('be.visible').click();

    cy.get('[data-testid="rich-text-editor"]').type('{selectall}');
    cy.get('[data-testid="clear-formatting-button"]').should('be.visible').click();

    cy.get('[data-testid="rich-text-editor"]').should('contain.text', 'item');
  });
}

export function insertLinkViaToolbar() {
  void cy.window().then((win) => {
    cy.stub(win, 'prompt').returns('https://orion.example').as('linkPrompt');
  });

  void visibleForm().within(() => {
    cy.get('[data-testid="rich-text-editor"]')
      .should('be.visible')
      .click()
      .type('Click here')
      .type('{selectall}');

    cy.get('[data-testid="insert-link-button"]').should('be.visible').click();
  });

  void cy.get('@linkPrompt').should('have.been.called');
  void cy.get('[data-testid="rich-text-editor"]').should('be.visible');
}

export function fillCcAndBcc(cc: string, bcc: string) {
  void visibleForm().within(() => {
    cy.get('[data-testid="cc-field"]')
      .should('be.visible')
      .find('[data-testid="cc-input"]')
      .clear()
      .type(cc)
      .should('have.value', cc);

    cy.get('[data-testid="bcc-field"]')
      .should('be.visible')
      .find('[data-testid="bcc-input"]')
      .clear()
      .type(bcc)
      .should('have.value', bcc);
  });
}

export function attachSmallFileAndRemove() {
  void visibleForm().within(() => {
    cy.get('[data-testid="file-input"]').selectFile(
      {
        contents: Cypress.Buffer.from('Cypress attachment contents'),
        fileName: 'note.txt',
        mimeType: 'text/plain',
      },
      { force: true }
    );

    cy.get('[data-testid="selected-attachment"]').should('be.visible').and('contain.text', 'note.txt');
    cy.get('[data-testid="total-file-size"]').should('be.visible').and('contain.text', 'MB');

    cy.get('[data-testid="remove-attachment-button"]').should('be.visible').click();
    cy.get('[data-testid="selected-attachment"]').should('not.exist');
    cy.get('[data-testid="total-file-size"]').should('not.exist');
  });
}

export function attachOversizedFileShowsError() {
  void visibleForm().within(() => {
    cy.get('[data-testid="file-input"]').selectFile(
      {
        contents: Cypress.Buffer.alloc(1200 * 1024, 'a'),
        fileName: 'too-big.bin',
        mimeType: 'application/octet-stream',
      },
      { force: true }
    );

    cy.get('[data-testid="file-error"]').should('be.visible').and('contain.text', 'larger than');
    cy.get('[data-testid="total-file-size"]').should('not.exist');
  });
}
