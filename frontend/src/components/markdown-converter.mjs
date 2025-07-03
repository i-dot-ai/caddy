// @ts-check

import { LitElement, html } from 'lit';
import { unsafeHTML } from 'lit-html/directives/unsafe-html.js';
import Showdown from 'showdown';


const MarkdownConverter = class extends LitElement {

  static properties = {
    content: { type: String },
  };

  /**
   * @param {string} markdown
   * @returns {string}
   */
  convert (markdown) {
    let converter = new Showdown.Converter({
      disableForced4SpacesIndentedSublists: true,
      headerLevelStart: 2,
      tables: true,
    });
    return converter.makeHtml(markdown);
  }

  createRenderRoot () {
    this.innerHTML = '';
    return this;
  }

  render () {
    return html`
      <div>
        ${unsafeHTML(this.convert(this.content))}
      </div>
    `;
  }

};

customElements.define('markdown-converter', MarkdownConverter);
