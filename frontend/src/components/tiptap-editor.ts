import { Editor } from '@tiptap/core';
import { StarterKit } from '@tiptap/starter-kit';
import { Typography } from '@tiptap/extension-typography';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { Link } from '@tiptap/extension-link';
import { Image } from '@tiptap/extension-image';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';

export class TiptapEditor {
  private editor: Editor | null = null;

  private originalContent: string;

  private toolbar: HTMLElement | null = null;

  private collectionId: string;

  private resourceId: string;

  constructor(private container: HTMLElement, private initialContent: string) {
    this.originalContent = initialContent;
    this.extractIds();
    this.init();
  }

  private extractIds() {
    // Extract collection and resource IDs from the current URL path
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
      this.editor = new Editor({
        element: editorContainer,
        content: this.convertMarkdownToHTML(this.initialContent),
        extensions: [
          StarterKit.configure({
            heading: {
              levels: [1, 2, 3, 4, 5, 6],
            },
          }),
          Typography,
          Table.configure({
            resizable: true,
          }),
          TableRow,
          TableHeader,
          TableCell,
          Link.configure({
            openOnClick: false,
          }),
          Image,
          TaskList,
          TaskItem.configure({
            nested: true,
          }),
        ],
        editorProps: {
          attributes: {
            class: 'tiptap-editor-content',
          },
        },
        onUpdate: () => {
          this.updateToolbarState();
        },
      });

      this.createToolbar();
      this.setupEventListeners();
      this.updateToolbarState();
    } catch(error) {
      console.error('Failed to initialize Tiptap editor:', error);
    }
  }

  private convertMarkdownToHTML(markdown: string): string {
    // Simple markdown to HTML conversion for basic cases
    return markdown
      .replace(/^# (.+$)/gim, '<h1>$1</h1>')
      .replace(/^## (.+$)/gim, '<h2>$1</h2>')
      .replace(/^### (.+$)/gim, '<h3>$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/~~(.*?)~~/g, '<s>$1</s>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  private convertHTMLToMarkdown(html: string): string {
    // Simple HTML to markdown conversion
    return html
      .replace(/<h1>(.*?)<\/h1>/g, '# $1\n')
      .replace(/<h2>(.*?)<\/h2>/g, '## $1\n')
      .replace(/<h3>(.*?)<\/h3>/g, '### $1\n')
      .replace(/<strong>(.*?)<\/strong>/g, '**$1**')
      .replace(/<em>(.*?)<\/em>/g, '*$1*')
      .replace(/<s>(.*?)<\/s>/g, '~~$1~~')
      .replace(/<code>(.*?)<\/code>/g, '`$1`')
      .replace(/<br>/g, '\n')
      .replace(/<[^>]*>/g, ''); // Remove any remaining HTML tags
  }

  private createToolbar() {
    if (!this.editor) return;

    const toolbar = document.createElement('div');
    toolbar.className = 'tiptap-toolbar';

    // Add inline styles to ensure proper toolbar appearance
    toolbar.style.cssText = `
      border-bottom: 1px solid #e5e7eb;
      padding: 8px 12px;
      background-color: #f8fafc;
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      position: sticky;
      top: 0;
      z-index: 10;
    `;

    toolbar.innerHTML = `
      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="undo" title="Undo" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">↶</button>
        <button type="button" data-command="redo" title="Redo" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">↷</button>
      </div>
      
      <div class="toolbar-separator" style="width: 1px; background: #e5e7eb; margin: 4px 8px;"></div>
      
      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="bold" title="Bold (Ctrl+B)" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;"><strong>B</strong></button>
        <button type="button" data-command="italic" title="Italic (Ctrl+I)" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;"><em>I</em></button>
        <button type="button" data-command="strikethrough" title="Strikethrough" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;"><s>S</s></button>
        <button type="button" data-command="code" title="Inline Code" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">&lt;/&gt;</button>
      </div>

      <div class="toolbar-separator" style="width: 1px; background: #e5e7eb; margin: 4px 8px;"></div>

      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="h1" title="Heading 1" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">H1</button>
        <button type="button" data-command="h2" title="Heading 2" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">H2</button>
        <button type="button" data-command="h3" title="Heading 3" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">H3</button>
      </div>

      <div class="toolbar-separator" style="width: 1px; background: #e5e7eb; margin: 4px 8px;"></div>

      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="bulletList" title="Bullet List" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">• List</button>
        <button type="button" data-command="orderedList" title="Numbered List" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">1. List</button>
        <button type="button" data-command="taskList" title="Task List" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">☑ Tasks</button>
      </div>

      <div class="toolbar-separator" style="width: 1px; background: #e5e7eb; margin: 4px 8px;"></div>

      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="blockquote" title="Quote" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">❝</button>
        <button type="button" data-command="codeBlock" title="Code Block" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">{ }</button>
        <button type="button" data-command="horizontalRule" title="Horizontal Line" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">―</button>
      </div>

      <div class="toolbar-separator" style="width: 1px; background: #e5e7eb; margin: 4px 8px;"></div>

      <div class="toolbar-group" style="display: flex; gap: 2px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 4px;">
        <button type="button" data-command="link" title="Add Link" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">🔗</button>
        <button type="button" data-command="image" title="Add Image" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">🖼</button>
        <button type="button" data-command="table" title="Insert Table" style="background: none; border: none; border-radius: 4px; padding: 6px 8px; cursor: pointer; font-size: 14px; color: #374151; transition: all 0.15s ease; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">⊞</button>
      </div>
    `;

    const editorElement = this.container.querySelector('#editor') as HTMLElement;
    editorElement.parentNode?.insertBefore(toolbar, editorElement);
    this.toolbar = toolbar;

    // Add event listeners for toolbar buttons
    toolbar.addEventListener('click', (e) => {
      const target = e.target as HTMLButtonElement;
      if (target.tagName === 'BUTTON') {
        this.handleToolbarCommand(target.dataset.command as string);
      }
    });

    // Add hover effects to toolbar buttons
    toolbar.addEventListener('mouseover', (e) => {
      const target = e.target as HTMLButtonElement;
      if (target.tagName === 'BUTTON') {
        target.style.backgroundColor = '#e5e7eb';
        target.style.color = '#111827';
      }
    });

    toolbar.addEventListener('mouseout', (e) => {
      const target = e.target as HTMLButtonElement;
      if (target.tagName === 'BUTTON' && !target.classList.contains('active')) {
        target.style.backgroundColor = 'transparent';
        target.style.color = '#374151';
      }
    });
  }

  private handleToolbarCommand(command: string) {
    if (!this.editor) return;

    const chain = this.editor.chain().focus();

    switch (command) {
      case 'undo':
        chain.undo().run();
        break;
      case 'redo':
        chain.redo().run();
        break;
      case 'bold':
        chain.toggleBold().run();
        break;
      case 'italic':
        chain.toggleItalic().run();
        break;
      case 'strikethrough':
        chain.toggleStrike().run();
        break;
      case 'code':
        chain.toggleCode().run();
        break;
      case 'h1':
        chain.toggleHeading({ level: 1 }).run();
        break;
      case 'h2':
        chain.toggleHeading({ level: 2 }).run();
        break;
      case 'h3':
        chain.toggleHeading({ level: 3 }).run();
        break;
      case 'bulletList':
        chain.toggleBulletList().run();
        break;
      case 'orderedList':
        chain.toggleOrderedList().run();
        break;
      case 'taskList':
        chain.toggleTaskList().run();
        break;
      case 'blockquote':
        chain.toggleBlockquote().run();
        break;
      case 'codeBlock':
        chain.toggleCodeBlock().run();
        break;
      case 'horizontalRule':
        chain.setHorizontalRule().run();
        break;
      case 'link':
        this.addLink();
        break;
      case 'image':
        this.addImage();
        break;
      case 'table':
        chain.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
        break;
    }

    this.updateToolbarState();
  }

  private addLink() {
    if (!this.editor) return;

    const url = prompt('Enter URL:');
    if (url) {
      this.editor.chain().focus().setLink({ href: url }).run();
    }
  }

  private addImage() {
    if (!this.editor) return;

    const url = prompt('Enter image URL:');
    if (url) {
      this.editor.chain().focus().setImage({ src: url }).run();
    }
  }

  private updateToolbarState() {
    if (!this.editor || !this.toolbar) return;

    // Update active states for formatting buttons
    const commands = {
      bold: this.editor.isActive('bold'),
      italic: this.editor.isActive('italic'),
      strikethrough: this.editor.isActive('strike'),
      code: this.editor.isActive('code'),
      h1: this.editor.isActive('heading', { level: 1 }),
      h2: this.editor.isActive('heading', { level: 2 }),
      h3: this.editor.isActive('heading', { level: 3 }),
      bulletList: this.editor.isActive('bulletList'),
      orderedList: this.editor.isActive('orderedList'),
      taskList: this.editor.isActive('taskList'),
      blockquote: this.editor.isActive('blockquote'),
      codeBlock: this.editor.isActive('codeBlock'),
    };

    Object.entries(commands).forEach(([command, isActive]) => {
      const button = this.toolbar?.querySelector(`[data-command="${command}"]`) as HTMLButtonElement;
      if (button) {
        if (isActive) {
          button.classList.add('active');
          button.style.backgroundColor = '#374151';
          button.style.color = 'white';
        } else {
          button.classList.remove('active');
          button.style.backgroundColor = 'transparent';
          button.style.color = '#374151';
        }
      }
    });
  }

  private setupEventListeners() {
    console.log('Setting up event listeners...');
    console.log('Container:', this.container);

    // Look for buttons in the parent container (tiptap-container)
    const parentContainer = this.container.parentElement;
    console.log('Parent container:', parentContainer);

    const saveBtn = parentContainer?.querySelector('#save-btn') as HTMLButtonElement;
    const cancelBtn = parentContainer?.querySelector('#cancel-btn') as HTMLButtonElement;

    console.log('Save button found:', !!saveBtn, saveBtn);
    console.log('Cancel button found:', !!cancelBtn, cancelBtn);

    if (saveBtn) {
      console.log('Adding click listener to save button');
      saveBtn.addEventListener('click', () => {
        console.log('Save button clicked!');
        this.saveContent();
      });
    } else {
      console.error('Save button not found in parent container');
    }

    if (cancelBtn) {
      console.log('Adding click listener to cancel button');
      cancelBtn.addEventListener('click', () => {
        console.log('Cancel button clicked!');
        this.cancelChanges();
      });
    } else {
      console.error('Cancel button not found in parent container');
    }
  }

  private async saveContent() {
    if (!this.editor) return;

    const parentContainer = this.container.parentElement;
    const saveBtn = parentContainer?.querySelector('#save-btn') as HTMLButtonElement;
    if (!saveBtn) return;

    // Show loading state
    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
      const html = this.editor.getHTML();
      const markdown = this.convertHTMLToMarkdown(html);

      const response = await fetch(`/api/collections/${this.collectionId}/resources/${this.resourceId}/single-document`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          page_content: markdown,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `Server error: ${response.status}`);
      }

      // Update original content to reflect the saved state
      this.originalContent = markdown;

      // Show success feedback
      saveBtn.textContent = 'Saved!';
      saveBtn.classList.add('govuk-button--success');

      // Reset button after 2 seconds
      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.classList.remove('govuk-button--success');
        saveBtn.disabled = false;
      }, 2000);

    } catch(error) {
      console.error('Failed to save content:', error);

      // Show error state
      saveBtn.textContent = 'Save Failed';
      saveBtn.classList.add('govuk-button--warning');

      // Reset button after 3 seconds
      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.classList.remove('govuk-button--warning');
        saveBtn.disabled = false;
      }, 3000);

      // Show error message to user
      alert(`Failed to save: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private cancelChanges() {
    if (!this.editor) return;

    try {
      const originalHTML = this.convertMarkdownToHTML(this.originalContent);
      this.editor.commands.setContent(originalHTML);
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
  console.log('DOMContentLoaded fired, initializing Tiptap editor...');
  const editorContainer = document.getElementById('tiptap-editor');
  const contentElement = document.getElementById('markdown-content');

  console.log('Editor container found:', !!editorContainer);
  console.log('Content element found:', !!contentElement);

  if (editorContainer && contentElement) {
    const content = contentElement.textContent || '';
    console.log('Creating TiptapEditor with content length:', content.length);
    try {
      new TiptapEditor(editorContainer, content);
      console.log('TiptapEditor created successfully');
    } catch(error) {
      console.error('Error creating TiptapEditor:', error);
    }
  } else {
    console.error('Missing required elements:', {
      editorContainer: !!editorContainer,
      contentElement: !!contentElement,
    });
  }
});
