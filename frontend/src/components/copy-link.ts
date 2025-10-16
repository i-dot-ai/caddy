const CopyLink = class extends HTMLElement {

  connectedCallback() {
    const button = this.querySelector('button');
    button?.addEventListener('click', () => {
      this.#copyToClipboard(button.dataset.url || '');
      button.textContent = 'Link copied';
    });
  }

  #copyToClipboard(url: string) {
    const listener = (evt: ClipboardEvent) => {
      evt.clipboardData?.setData('text/html', url);
      evt.clipboardData?.setData('text/plain', url);
      evt.preventDefault();
    };
    document.addEventListener('copy', listener);
    document.execCommand('copy');
    document.removeEventListener('copy', listener);
  }

};

customElements.define('copy-link', CopyLink);
