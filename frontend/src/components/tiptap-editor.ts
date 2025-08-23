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

  constructor(private container: HTMLElement, private initialContent: string) {
    this.originalContent = initialContent;
    this.init();
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
    toolbar.innerHTML = `
      <div class="toolbar-group">
        <button type="button" data-command="undo" title="Undo">↶</button>
        <button type="button" data-command="redo" title="Redo">↷</button>
      </div>
      
      <div class="toolbar-separator"></div>
      
      <div class="toolbar-group">
        <button type="button" data-command="bold" title="Bold (Ctrl+B)"><strong>B</strong></button>
        <button type="button" data-command="italic" title="Italic (Ctrl+I)"><em>I</em></button>
        <button type="button" data-command="strikethrough" title="Strikethrough"><s>S</s></button>
        <button type="button" data-command="code" title="Inline Code">&lt;/&gt;</button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button type="button" data-command="h1" title="Heading 1">H1</button>
        <button type="button" data-command="h2" title="Heading 2">H2</button>
        <button type="button" data-command="h3" title="Heading 3">H3</button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button type="button" data-command="bulletList" title="Bullet List">• List</button>
        <button type="button" data-command="orderedList" title="Numbered List">1. List</button>
        <button type="button" data-command="taskList" title="Task List">☑ Tasks</button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button type="button" data-command="blockquote" title="Quote">❝</button>
        <button type="button" data-command="codeBlock" title="Code Block">{ }</button>
        <button type="button" data-command="horizontalRule" title="Horizontal Line">―</button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button type="button" data-command="link" title="Add Link">🔗</button>
        <button type="button" data-command="image" title="Add Image">🖼</button>
        <button type="button" data-command="table" title="Insert Table">⊞</button>
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
      const button = this.toolbar?.querySelector(`[data-command="${command}"]`);
      if (button) {
        button.classList.toggle('active', isActive);
      }
    });
  }

  private setupEventListeners() {
    const saveBtn = this.container.querySelector('#save-btn') as HTMLButtonElement;
    const cancelBtn = this.container.querySelector('#cancel-btn') as HTMLButtonElement;

    if (saveBtn) {
      saveBtn.addEventListener('click', () => this.saveContent());
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this.cancelChanges());
    }
  }

  private saveContent() {
    if (!this.editor) return;

    try {
      const html = this.editor.getHTML();
      const markdown = this.convertHTMLToMarkdown(html);

      // Here you would typically send the markdown to your backend
      console.log('Saving content:', markdown);
      alert('Content saved successfully!');
    } catch(error) {
      console.error('Failed to save content:', error);
      alert('Failed to save content');
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
  const editorContainer = document.getElementById('tiptap-editor');
  const contentElement = document.getElementById('markdown-content');

  if (editorContainer && contentElement) {
    const content = contentElement.textContent || '';
    new TiptapEditor(editorContainer, content);
  }
});
