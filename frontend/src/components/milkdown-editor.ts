import { Crepe } from '@milkdown/crepe';
import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';
import { replaceAll } from '@milkdown/utils';
import { updateSingleResource } from '../logic/data.ts';

export class MilkdownEditor {
  private editor: Crepe | null = null;

  private originalContent: string;

  private collectionId: string;

  private resourceId: string;

  constructor(private container: HTMLElement, private initialContent: string) {
    this.originalContent = initialContent;
    this.extractIds();
    this.init();
  }

  private extractIds() {
    const pathParts = window.location.pathname.split('/');
    const collectionsIndex = pathParts.indexOf('collections');
    const resourcesIndex = pathParts.indexOf('resources');

    if (collectionsIndex !== -1 && resourcesIndex !== -1) {
      this.collectionId = pathParts[collectionsIndex + 1];
      this.resourceId = pathParts[resourcesIndex + 1];
    } else {
      throw new Error('Unable to extract collection and resource IDs from URL');
    }
  }

  private async init() {
    const editorContainer = this.container.querySelector('#editor') as HTMLElement;

    if (!editorContainer) {
      console.error('Editor container not found');
      return;
    }

    try {
      this.editor = new Crepe({
        root: editorContainer,
        defaultValue: this.initialContent || '',
      });

      await this.editor.create();
      this.setupEventListeners();
    } catch(error) {
      console.error('Failed to initialize Milkdown Crepe editor:', error);
      console.error('Error stack:', error?.stack);
    }
  }

  private async getContent(): Promise<string> {
    if (!this.editor) return '';

    try {
      return this.editor.getMarkdown();
    } catch(error) {
      console.error('Error getting content:', error);
      return this.originalContent;
    }
  }

  private async setContent(markdown: string) {
    if (!this.editor) return;

    try {
      await this.editor.editor.action(replaceAll(markdown));
    } catch(error) {
      console.error('Error setting content:', error);
    }
  }


  private setupEventListeners() {
    const parentContainer = this.container.parentElement;
    const saveBtn = parentContainer?.querySelector('#save-btn') as HTMLButtonElement;
    const cancelBtn = parentContainer?.querySelector('#cancel-btn') as HTMLButtonElement;

    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        this.saveContent();
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        this.cancelChanges();
      });
    }
  }

  private async saveContent() {
    if (!this.editor) return;

    const parentContainer = this.container.parentElement;
    const saveBtn = parentContainer?.querySelector('#save-btn') as HTMLButtonElement;
    if (!saveBtn) return;

    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
      const markdown = await this.getContent();

      // Call the data layer function (which uses the frontend API proxy)
      const { error } = await updateSingleResource(this.collectionId, this.resourceId, markdown, null);

      if (error) {
        throw new Error(error);
      }

      this.originalContent = markdown;

      saveBtn.textContent = 'Saved!';
      saveBtn.classList.add('govuk-button--success');

      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.classList.remove('govuk-button--success');
        saveBtn.disabled = false;
      }, 2000);

    } catch(error) {
      console.error('Failed to save content:', error);

      saveBtn.textContent = 'Save Failed';
      saveBtn.classList.add('govuk-button--warning');

      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.classList.remove('govuk-button--warning');
        saveBtn.disabled = false;
      }, 3000);

      alert(`Failed to save: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private cancelChanges() {
    if (!this.editor) return;

    try {
      this.setContent(this.originalContent);
    } catch(error) {
      console.error('Failed to cancel changes:', error);
    }
  }

  public destroy() {
    if (this.editor) {
      this.editor.destroy();
    }
  }
}

// Initialize the editor when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const editorContainer = document.getElementById('milkdown-editor');
  const contentElement = document.getElementById('markdown-content');

  if (editorContainer && contentElement) {
    const content = contentElement.textContent || '';
    try {
      new MilkdownEditor(editorContainer, content);
    } catch(error) {
      console.error('Error creating MilkdownEditor:', error);
    }
  } else {
    console.error('Missing required elements:', {
      editorContainer: !!editorContainer,
      contentElement: !!contentElement,
    });
  }
});
