/**
 * Makes tables sortable
 * Wrap the table inside <sortable-table> <sortable-table>
 * Add the data-sortable attribute to any <th> elements that can allow sorting
 * Optional: Add a default aria-sort="ascending" attribute to any column that is sorted by default on page load
 * Optional: The default sorting runs on the visible text for that column. You can override this by providing a data-sort attribute on a <td>, e.g. useful for dates/times
 */


const SortableTable = class extends HTMLElement {

  connectedCallback() {

    // Add buttons to all sortable columns
    this.querySelectorAll('[data-sortable]').forEach((column) => {

      column.innerHTML = `
        <button>
          ${column.textContent}
          <span class="govuk-visually-hidden"> - sort</span>
        </button>
      `;

      column.querySelector('button')?.addEventListener('click', () => {
        if (column.getAttribute('aria-sort') === 'ascending') {
          this.querySelectorAll('[data-sortable]').forEach((column) => column.removeAttribute('aria-sort'));
          column.setAttribute('aria-sort', 'descending');
        } else {
          this.querySelectorAll('[data-sortable]').forEach((column) => column.removeAttribute('aria-sort'));
          column.setAttribute('aria-sort', 'ascending');
        }
        this.#sort();
      });

    });

  }


  #sort() {

    // what column are we sorting by and in which direction?
    const { columnIndex, direction } = (() => {
      let columnIndex = -1;
      let direction = '';
      this.querySelectorAll('th').forEach((column, index) => {
        if (column.hasAttribute('aria-sort')) {
          columnIndex = index;
          direction = column.getAttribute('aria-sort') || 'ascending';
        }
      });
      return { columnIndex, direction };
    })();

    // sort rows - look for data-sort attribute for special cases (e.g. dates), otherwise just look at text
    const sortedRows = [...this.querySelectorAll('tbody tr')].sort((rowA, rowB) => {
      const cellA = rowA.querySelector(`td:nth-child(${columnIndex + 1})`);
      const cellB = rowB.querySelector(`td:nth-child(${columnIndex + 1})`);
      const contentA = cellA?.getAttribute('data-sort') || cellA?.textContent?.trim() || '';
      const contentB = cellB?.getAttribute('data-sort') || cellB?.textContent?.trim() || '';
      return (contentA > contentB ? 1 : -1) * (direction === 'ascending' ? 1 : -1);
    });

    // update table with sorted rows
    const tbody = this.querySelector('tbody') as HTMLElement;
    tbody.innerHTML = '';
    sortedRows.forEach((row) => tbody.appendChild(row));

  }

};

customElements.define('sortable-table', SortableTable);
