import path from 'path';
import { fileURLToPath } from 'url';
import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';


const testAccessibility = async(page: Page) => {
  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  expect(accessibilityScanResults.violations).toEqual([]);
};


/**
 * Finds the row some specific text appears on (index starts from 1)
 */
const getRowIndex = async(text: string, page: Page) => {
  const index = await page.evaluate((text) => {
    let matchingIndex = -1;
    document.querySelectorAll('tbody tr').forEach((row, rowIndex) => {
      if (row.querySelector('td')?.textContent?.includes(text)) {
        matchingIndex = rowIndex;
      }
    });
    return matchingIndex;
  }, text);
  return index + 1;
};


test('Manage collections', async({ page }) => {

  // Collections page (1)
  await page.goto('localhost:4322/');
  await expect(page.locator('h2').last()).toContainText('Collections');
  await testAccessibility(page);
  await page.getByText('Add a collection').click();

  // Add collection page
  await expect(page.locator('h1')).toContainText('Add a collection');
  await testAccessibility(page);
  const collectionName = `test-collection-${Date.now()}`;
  await page.getByLabel('Collection name').fill(collectionName);
  await page.getByLabel('Description').fill('Added by Playwright');
  await page.locator('button:has-text("Add")').click();

  // Collections page (2)
  await expect(page.locator('h2').last()).toContainText('Collections');
  await expect(page.locator('.govuk-panel__body')).toContainText(`Collection ${collectionName} created`);
  await expect(page.locator(`span:has-text("${collectionName}")`).first()).toBeVisible();
  let newCollectionIndex = await getRowIndex(collectionName, page);
  await page.locator(`tbody tr:nth-child(${newCollectionIndex}) a:has-text("Edit")`).click();

  // Edit collection page
  await expect(page.locator('h1')).toContainText('Edit collection');
  await testAccessibility(page);
  expect(await page.getByLabel('Collection name').inputValue()).toEqual(collectionName);
  expect(await page.getByLabel('Description').inputValue()).toEqual('Added by Playwright');
  const testDescription = `Description set at ${Date.now()}`;
  await page.getByLabel('Description').fill(testDescription);
  await page.locator('button:has-text("Update")').click();

  // Collections page (3)
  await expect(page.locator('h2').last()).toContainText('Collections');
  await expect(page.locator('.govuk-panel__body')).toContainText(`Collection ${collectionName} updated`);
  await expect(page.locator(`span:has-text("${collectionName}")`).first()).toBeVisible();
  await expect(page.locator(`span:has-text("${testDescription}")`)).toBeVisible();
  newCollectionIndex = await getRowIndex(collectionName, page);
  await page.locator(`tbody tr:nth-child(${newCollectionIndex}) a:has-text("Delete")`).click();

  // Delete collection page
  await expect(page.locator('h1')).toContainText('Delete collection');
  await testAccessibility(page);
  await expect(page.getByText(collectionName)).toBeVisible();
  await page.locator('button:has-text("Confirm delete")').click();

  // Collections page (4)
  await expect(page.locator('h2').last()).toContainText('Collections');
  await expect(page.locator('.govuk-panel__body')).toContainText(`Collection ${collectionName} deleted`);
  expect(await page.locator(`span:has-text("${collectionName}")`).count()).toEqual(0);

});


test('Manage resources', async({ page }) => {

  // Collections page
  await page.goto('localhost:4322/');
  await expect(page.locator('h2').last()).toContainText('Collections');
  const collectionName = await page.locator('td span').first().innerText();
  await page.locator('td a').first().click();

  // Resources page (1)
  await expect(page.locator('h1')).toContainText('Resources');
  await expect(page.locator(`p:has-text("${collectionName}")`)).toBeVisible();
  const resourceCount = await page.locator('tbody tr').count();
  await page.locator('a:has-text("Add resource")').click();

  // Upload page
  await expect(page.locator('h1')).toContainText('Add resource(s)');
  await expect(page.getByText(collectionName)).toBeVisible();
  await testAccessibility(page);
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const fileChooserPromise = page.waitForEvent('filechooser');
  await page.locator('input[type="file"]').click({ clickCount: 2 });
  const fileChooser = await fileChooserPromise;
  fileChooser.setFiles(path.join(__dirname, '../README.md'));
  await page.locator('Button:has-text("Add file(s)")').click();
  await page.locator('a:has-text("Back to resources page")').click();

  // Resources page (2)
  await expect(page.locator('h1')).toContainText('Resources');
  await testAccessibility(page);
  expect(await page.locator('tbody tr').count()).toEqual(resourceCount + 1);
  const rowIndex = await getRowIndex('README.md', page);
  await page.locator(`tbody tr:nth-child(${rowIndex}) a:has-text("Delete")`).click();

  // Delete resource page
  await expect(page.locator('h1')).toContainText('Delete resource');
  await testAccessibility(page);
  await page.getByText('Confirm delete').click();

  // Resources page (3)
  await expect(page.locator('h1')).toContainText('Resources');
  await expect(page.locator('.govuk-panel__body')).toContainText('Resource README.md deleted');
  expect(await page.locator('tbody tr').count()).toEqual(resourceCount);
  const resourceLink = page.locator('td a').first();
  const resourceName = await resourceLink.innerText();
  await resourceLink.click();

  // Resource details page
  await expect(page.locator('h1')).toContainText('Resource details');
  await expect(page.getByText(resourceName)).toBeVisible();
  await testAccessibility(page);
  await page.locator('a:has-text("Resources")').click();

  // Resources page (4)
  await expect(page.locator('h1')).toContainText('Resources');

});


test('Manage users', async({ page }) => {

  // Collections page
  await page.goto('localhost:4322/');
  await page.locator('td a:has-text("Users")').first().click();

  // Users page (1)
  await expect(page.locator('h1')).toContainText('Users');
  await testAccessibility(page);
  const userCount1 = await page.locator('tbody tr').count();
  await page.locator('a:has-text("Add user")').click();

  // Add user page
  await expect(page.locator('h1')).toContainText('Add user');
  await testAccessibility(page);
  const emailAddress = `${Date.now()}@test.com`;
  await page.getByLabel('Email address').fill(emailAddress);
  await page.locator('button:has-text("Add user")').click();

  // Users page (2)
  await expect(page.locator('h1')).toContainText('Users');
  await expect(page.locator('.govuk-panel__body')).toContainText(`User ${emailAddress} added to collection`);
  const userCount2 = await page.locator('tbody tr').count();
  expect(userCount2).toEqual(userCount1 + 1);
  await expect(page.locator(`td:has-text("${emailAddress}")`).first()).toBeVisible();
  let index = await getRowIndex(emailAddress, page);
  expect(await page.locator(`tbody tr:nth-child(${index}) td:nth-child(2)`).innerText()).toEqual('User');
  await page.locator(`tr:nth-child(${index}) a:has-text("Edit")`).last().click();

  // Edit user page
  await expect(page.locator('h1')).toContainText('Edit user');
  await testAccessibility(page);
  await page.getByLabel('Role').selectOption('manager');
  await page.locator('button:has-text("Update user")').click();

  // Users page (3)
  await expect(page.locator('h1')).toContainText('Users');
  await expect(page.locator('.govuk-panel__body')).toContainText(`User ${emailAddress} updated`);
  index = await getRowIndex(emailAddress, page);
  expect(await page.locator(`tbody tr:nth-child(${index}) td:nth-child(2)`).innerText()).toEqual('Admin');
  await page.locator(`tr:nth-child(${index}) a:has-text("Remove")`).last().click();

  // Remove user page
  await expect(page.locator('h1')).toContainText('Remove user');
  await testAccessibility(page);
  await page.locator('button:has-text("Confirm remove")').click();

  // Users page (4)
  await expect(page.locator('h1')).toContainText('Users');
  await expect(page.locator('.govuk-panel__body')).toContainText(`User ${emailAddress} removed from collection`);
  const userCount3 = await page.locator('tbody tr').count();
  expect(userCount3).toEqual(userCount1);

});
