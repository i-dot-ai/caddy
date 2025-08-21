/**
 * Shows message while URLs are being processed
 * Wrap it around the submit button
 */


const AddUrls = class extends HTMLElement {

  connectedCallback() {
    this.querySelector('button')?.addEventListener('click', () => {
      window.setTimeout(() => {
        this.innerHTML = `
          <p class="govuk-body loading-ellipsis" tabindex="-1">
            The URLs are currently being processed. Please wait
            <span aria-hidden="true">.</span>
            <span aria-hidden="true">.</span>
            <span aria-hidden="true">.</span>
          </p>
        `;
        window.setTimeout(() => {
          this.querySelector('p')?.focus();
        }, 100);
      }, 100);
    });

  }

};

customElements.define('add-urls', AddUrls);
