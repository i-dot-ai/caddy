/**
 * Flags any duplicate URLs about to be added (also matches with/without trailing slashes)
 * Requires data-textarea attribute containing the ID of the textarea to check for new URLs
 * Requires data-existing-urls attribute containing an array of existing URLs to check - string[]
 * Optional: Add any non-js content inside <duplicate-urls> <duplicate-urls> - this will be removed once the javascript takes over
 */


const DuplicateUrls = class extends HTMLElement {

  connectedCallback() {

    // listen for textarea changes
    if (!this.dataset.textarea) {
      return;
    }
    const textarea = document.getElementById(this.dataset.textarea) as HTMLTextAreaElement;
    textarea?.addEventListener('keyup', () => {
      this.#showDuplicates(textarea.value);
    });

    // clear existing content
    this.innerHTML = '';

  }


  #showDuplicates(newUrlContent: string) {

    const newUrls = newUrlContent.split(/\r?\n/)
      .map((line) => line.trim().replace(/\/$/g, ''));
    const existingUrls: string[] = JSON.parse(this.dataset.existingUrls || '[]');
    const duplicates = existingUrls.filter((existingUrl) => newUrls.includes(existingUrl.replace(/\/$/g, '')));

    if (duplicates.length) {
      this.innerHTML = `
        <div class="govuk-warning-text">
          <span class="govuk-warning-text__icon" aria-hidden="true">!</span>
          <strong class="govuk-warning-text__text">
            <span class="govuk-visually-hidden">Important</span>
            The following URLs already exist in the collection and will be overwritten:
            <ul class="govuk-list govuk-list--bullet govuk-!-margin-top-1">
              ${duplicates.map((duplicate) => `
                <li>${duplicate}</li>
              `).join('\n')}
            </ul>
          </strong>
        </div>
      `;
    } else {
      this.innerHTML = '';
    }

  }


};

customElements.define('duplicate-urls', DuplicateUrls);
