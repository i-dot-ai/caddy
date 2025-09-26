// @ts-check

import { LitElement, html } from 'lit';


const IaiHeader = class extends LitElement {

  static properties = {
    productName: { type: String, attribute: 'product-name' },
  };

  createRenderRoot() {
    this.innerHTML = '';
    return this;
  }

  render() {
    return html`
      <header class="govuk-header govuk-header--full-width-border" data-module="govuk-header">
        <div class="govuk-header__container govuk-width-container">
          <div class="govuk-header__logo">
            <a href="/" class="govuk-header__link govuk-header__link--homepage">
              <span class="font-bold">AI.GOV.UK</span>
              <span class="govuk-header__product-name">${this.productName}</span>
            </a>
          </div>
        </div>
      </header>
    `;
  }

};

customElements.define('iai-header', IaiHeader);
