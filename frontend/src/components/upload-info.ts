const UploadInfo = class extends HTMLElement {

  private form: HTMLFormElement | null = null;
  
  connectedCallback() {

    this.form = document.querySelector('form');
    this.form?.addEventListener('submit', async (evt) => {
      evt.preventDefault();
      this.form?.classList.add('form-submitted');
      await this.#uploadFiles();
      window.location.href = this.getAttribute('resources-page') || window.location.href;
    });

  }


  #render() {

    this.innerHTML = `
      <div class="upload-info__ellipsis govuk-body govuk-!-font-weight-bold">
        <span id="upload-info__count" aria-live="assertive">Uploading file(s)</span>
        <span aria-hidden="true">.</span>
        <span aria-hidden="true">.</span>
        <span aria-hidden="true">.</span>
      </div>
    `;

    this.classList.add('upload-info');
    this.setAttribute('tabindex', '-1');
    window.setTimeout(() => {
      this.focus();
    }, 1);

  }


  async #uploadFiles() {

    // get files
    const fileInput = document.querySelector(`#${this.getAttribute('input-id')}`) as HTMLInputElement;
    const collectionId = this.getAttribute('collection') || '';
    const files = [...(fileInput.files || [])];

    this.#render();

    // send each file one at a time
    for (let fileIndex = 0; fileIndex < files.length; fileIndex ++) {
      (this.querySelector('#upload-info__count') as HTMLElement).textContent = `Uploading file ${fileIndex + 1} of ${files.length}`;
      const file = files[fileIndex];
      console.log(`Uploading: ${file.name}`);
      const formData = new FormData();
      formData.append('collection', collectionId);
      formData.append(fileInput.name, file);
      const response = await fetch(this.form?.action || '', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        console.error(`Upload failed for ${file.name}: ${response.statusText}`);
      }
    }

  }

}

customElements.define("upload-info", UploadInfo);
