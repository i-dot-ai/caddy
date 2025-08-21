/**
 * Shows files being uploaded along with their current status
 */


const UploadInfo = class extends HTMLElement {

  private form: HTMLFormElement | null = null;

  private fileInput: HTMLInputElement | null = null;

  connectedCallback() {

    this.fileInput = document.querySelector(`[name="${this.getAttribute('input-name')}"]`);
    this.form = this.fileInput?.closest('form') as HTMLFormElement | null;

    this.form?.addEventListener('submit', async(evt) => {
      evt.preventDefault();
      await this.#uploadFiles();
      this.querySelector('[hidden]')?.classList.add('govuk-button');
    });

  }


  #render(files: File[]) {

    this.innerHTML = `
      <h2 class="govuk-heading-m govuk-!-margin-top-7">Uploading files</h2>
      <ul class="govuk-task-list">
        ${files.map((file) => `
          <li class="govuk-task-list__item">
            <div class="govuk-task-list__name-and-hint">${file.name}</div>
            <div class="govuk-task-list__status">
              <strong class="govuk-tag govuk-tag--grey">Queued</strong>
            </div>
          </li>
        `).join('')}
      </ul>
      <a href="../resources" hidden>Back to resources page</a>
    `;

    this.classList.add('upload-info');
    this.setAttribute('tabindex', '-1');
    window.setTimeout(() => {
      this.focus();
    }, 1);

  }


  async #uploadFiles() {

    // get files
    const collectionId = this.getAttribute('collection') || '';
    const files = [...this.fileInput?.files || []];

    this.#render(files);
    const fileStatuses = this.querySelectorAll('.govuk-tag');

    // send each file one at a time
    for (let fileIndex = 0; fileIndex < files.length; fileIndex++) {

      const file = files[fileIndex];

      fileStatuses[fileIndex].className = 'govuk-tag govuk-tag--blue';
      fileStatuses[fileIndex].textContent = 'Uploading';

      const formData = new FormData();
      formData.append('collection', collectionId);
      formData.append(this.fileInput?.name || '', file);
      const response = await fetch(this.form?.action || '', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        console.error(`Upload failed for ${file.name}: ${response.statusText}`);
        fileStatuses[fileIndex].className = 'govuk-tag govuk-tag--red';
        fileStatuses[fileIndex].textContent = 'Error';
      } else {
        fileStatuses[fileIndex].className = 'govuk-tag govuk-tag--green';
        fileStatuses[fileIndex].textContent = 'Complete';
      }
    }

  }

};

customElements.define('upload-info', UploadInfo);
