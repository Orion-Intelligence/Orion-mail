const SIGNATURE_ARMOR = /^-----BEGIN PGP SIGNATURE-----\r?\n[\s\S]*\r?\n-----END PGP SIGNATURE-----$/;

/** Split only Orion's complete generated footer. Never change the stored message. */
export function splitTextIdentityFooter(body: string): { body: string; identity: string } {
  const footer = /\r?\n\r?\n--\r?\nSigned Identity Text:\r?\n([\s\S]*?)\r?\n\r?\nPGP Signature:\r?\n(-----BEGIN PGP SIGNATURE-----\r?\n[\s\S]*?\r?\n-----END PGP SIGNATURE-----)\s*$/.exec(body);
  if (!footer) {
    return { body, identity: '' };
  }
  return { body: body.slice(0, footer.index), identity: footer[1] ?? '' };
}

/** Match the five trailing elements emitted by build_identity_signature_block_html. */
export function removeHtmlIdentityFooter(document: Document): string {
  const nodes = Array.from(document.body.childNodes).filter(node => node.nodeType !== 3 || node.textContent?.trim());
  const footer = nodes.slice(-5);
  if (footer.length !== 5 || footer.some(node => node.nodeType !== 1)) {
    return '';
  }
  const [divider, identityLabel, identity, signatureLabel, signature] = footer as Element[];
  if (divider?.tagName !== 'HR' || identityLabel?.tagName !== 'P' || identity?.tagName !== 'PRE'
    || signatureLabel?.tagName !== 'P' || signature?.tagName !== 'PRE'
    || identityLabel.textContent?.trim() !== 'Signed Identity Text:'
    || signatureLabel.textContent?.trim() !== 'PGP Signature:'
    || !SIGNATURE_ARMOR.test(signature.textContent?.trim() ?? '')) {
    return '';
  }
  const text = identity.textContent ?? '';
  footer.forEach(node => node.parentNode?.removeChild(node));
  return text;
}
