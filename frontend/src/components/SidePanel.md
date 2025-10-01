# i.AI Side Panel component


## Page layout

Use as part of the following layout (you can ignore the govuk classes if required):

```
<body class="govuk-template__body govuk-frontend-supported relative lg:flex">

  <SidePanel productName="Product Name" productLogo="/path-to-logo.png">
    <!-- side panel content to go here -->
  </SidePanel>

  <div class="overflow-y-auto w-full lg:h-screen" id="scroll-panel">
    <div class="govuk-width-container ml-17! sm:ml-20! lg:mx-auto! lg:px-4">
      <main class="govuk-main-wrapper pb-0! pt-4!">
        <slot/>
      </main>
    </div>
  </div>

</body>
```

This may need modifying slightly if not using the gov.uk design system


## Useful notes

- Add the `sidepanel__hide-on-collapse` class to any elements that shouldn't be shown in the collapsed state

- This is based on Tailwind being set up with 5px spacing in order to work with the gov.uk Design System:
```
@theme {
  --spacing: 5px;
}
```


## Roadmap

- Update to work with the more common 4px spacing

- Consider adding an array of items instead of the slot for custom HTML (allowing for headings, links, plain text, dividers)
