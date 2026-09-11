export function createTestMail(
  receiver: string,
  subject: string,
  body: string
) {
  cy.setCookie('orion_mail_test_session', 'test2');

  return cy.request({
    method: 'POST',
    url: '/messages/send',
    form: true,
    headers: {
      'x-requested-with': 'XMLHttpRequest',
    },
    body: {
      receiver_address: receiver,
      subject,
      body,
    },
  }).then((response) => {
    expect(response.status).to.eq(200);
  });
}

export function loginAsTestUser(username: string) {
  void cy.setCookie('orion_mail_test_session', username);
}
