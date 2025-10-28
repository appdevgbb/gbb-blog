# Contributing to Azure Global Blackbelt Blog

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

- [Code of Conduct](#coc)
- [Issues and Bugs](#issue)
- [Feature Requests](#feature)
- [Submission Guidelines](#submit)

## Code of Conduct {#coc}

Help us keep this project open and inclusive. Please read and follow our [Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## Found an Issue? {#issue}

If you find a bug in the source code or a mistake in the documentation, you can help us by
[submitting an issue](#submit-issue) to the GitHub Repository. Even better, you can
[submit a Pull Request](#submit-pr) with a fix.

## Want a Feature? {#feature}

You can _request_ a new feature by [submitting an issue](#submit-issue) to the GitHub
Repository. If you would like to _implement_ a new feature, _please submit an issue with
a proposal for your work first, to be sure that we can use it_.

- **Small Features** can be crafted and directly [submitted as a Pull Request](#submit-pr).

### Submitting an Issue {#submit-issue}

Before you submit an issue, search the archive, maybe your question was already answered.

If your issue appears to be a bug, and hasn't been reported, open a new issue.
Help us to maximize the effort we can spend fixing issues and adding new
features, by not reporting duplicate issues. Providing the following information will increase the
chances of your issue being dealt with quickly:

- **Overview of the Issue** - if an error is being thrown a non-minified stack trace helps
- **Version** - what version is affected (e.g. 0.1.2)
- **Motivation for or Use Case** - explain what are you trying to do and why the current behavior is a bug for you
- **Browsers and Operating System** - is this a problem with all browsers?
- **Reproduce the Error** - provide a live example or a unambiguous set of steps
- **Related Issues** - has a similar issue been reported before?
- **Suggest a Fix** - if you can't fix the bug yourself, perhaps you can point to what might be
  causing the problem (line of code or commit)

You can file new issues by providing the above information at the corresponding repository's issues link: [https://github.com/appdevgbb/gbb-blog/issues/new](https://github.com/appdevgbb/gbb-blog/issues/new).

### Submitting a Pull Request (PR) {#submit-pr}

Before you submit your Pull Request (PR) consider the following guidelines:

- Search the repository [https://github.com/appdevgbb/gbb-blog/pulls](https://github.com/appdevgbb/gbb-blog/pulls) for an open or closed PR
  that relates to your submission. You don't want to duplicate effort.
- Fork the repository and make your changes in your local fork.
- Commit your changes using a descriptive commit message
- Push your fork to GitHub:
- In GitHub, create a pull request
- If we suggest changes then:

  - Make the required updates.
  - Rebase your fork and force push to your GitHub repository (this will update your Pull Request):

    ```shell
    git rebase main -i
    git push -f
    ```

## Submission Guidelines {#submit}

When creating a blog post, each post should be self-contained and focus on providing practical, actionable insights. Consider the time commitment required from readers - aim for posts that can be read and understood in **15-20 minutes**, with hands-on examples that can be completed in under an hour.

### Before You Author {#before-author}

Before creating content, check if your topic is already well-covered in Microsoft Learn or official Azure documentation. We want to provide unique value beyond what's already available. Focus on:

- Real-world scenarios and implementation patterns
- Integration examples with multiple Azure services
- Troubleshooting guides and best practices learned from field experience
- Deep dives into specific features or use cases

We particularly value content that demonstrates practical solutions to common challenges encountered in Azure deployments, especially around:

- Kubernetes (AKS) advanced configurations and integrations
- Security and identity management
- DevOps and CI/CD patterns
- Cloud-native application patterns
- Performance optimization

### Getting Started {#getting-started}

To get started, you will need to fork this repository and clone it to your local machine. When you are ready to submit your blog post, you can create a pull request to the main branch of this repository.

The site requires [Node.js](https://nodejs.org/en/download) to run locally. If you don't have Node.js installed locally, you can open this repo in [GitHub Codespaces](https://github.com/features/codespaces) or in a local DevContainer using [VS Code](https://code.visualstudio.com/docs/remote/containers) with Docker Desktop installed.

### Style Guide {#style-guide}

This blog is built using [Docusaurus](https://docusaurus.io/) and uses its default blog theme. If you have never authored with Docusaurus before, check out their [tutorial](https://tutorial.docusaurus.io/docs/tutorial-basics/markdown-features) for a quick introduction. Also, be sure to check out the other blog posts in the `docusaurus/blog` folder for examples of how to format your content.

### Creating Blog Posts {#creating-posts}

Blog posts are created as markdown files in the `docusaurus/blog` directory. Name your file using the format `YYYY-MM-DD-post-slug.md` (e.g., `2025-01-15-workload-identity-example.md`). The date in the filename determines when the post was published.

### Writing Content {#writing-content}

At the top of the markdown file, you will need to add front matter. The front-matter needs to be enclosed with three consecutive dashes `---` and include at minimum:

- `title`: The title of your blog post
- `authors`: The author(s) of the post (must match entries in `docusaurus/blog/authors.yml`)
- `tags`: Relevant tags for categorization

Here is an example:

```markdown
---
title: Your Blog Post Title
authors: [steve_griffith, diego_casati]
tags: [AKS, Kubernetes, Security, WorkloadIdentity]
---

Your content here...
```

The remaining content of the blog post can be written using standard markdown with additional [features](https://docusaurus.io/docs/markdown-features) provided by Docusaurus.

A typical blog post structure:

```markdown
---
title: Your Blog Post Title
authors: [author_name]
tags: [tag1, tag2, tag3]
---

Brief introduction paragraph that appears in the post preview.

<!-- truncate -->

The rest of your content appears after clicking "Read more". Include:
- Problem statement or context
- Solution or approach
- Code examples and screenshots
- Conclusion and key takeaways
```

### Directory Structure {#directory-structure}

If your blog post requires additional files, such as code samples or images, create a folder in `docusaurus/static/img/` using the same date format as your post filename (e.g., `2025-01-15-post-slug/`). Reference images using `/img/2025-01-15-post-slug/image.png`.

### Improving Accessibility {#improving-accessibility}

When authoring your blog post, please consider the accessibility of the content. This includes ensuring that the content is readable by screen readers and that any images included are accessible to all users.

When writing your content, please use headings to structure your content. This will help users who are using screen readers to navigate the content more easily.

#### Images

When taking screenshots, please use "light mode" where possible and ensure your monitor is set to a resolution of 1920x1080. This will ensure that the images are large enough to be readable by all users. Also, please be sure to include alt text for images so that users who are using screen readers can understand the content of the image.

#### URLs

If you are including URLs to refer readers to additional resources on Microsoft Learn, please ensure to remove any locale-specific URLs and use the global URLs instead. This will ensure that all users can access the content in their preferred language.

### Testing Locally {#test-locally}

To render the blog locally, open a terminal and run following commands from the `docusaurus` directory:

```shell
cd docusaurus
npm install
npm start
```

This will start a local server that you can access at [http://localhost:3000](http://localhost:3000) to see your changes.

### Testing Remotely {#test-remotely}

You may also want to have others review your blog post prior to submitting a PR. To test your changes remotely or share a publicly accessible URL with team members, you can deploy your changes to a GitHub Pages site by following these steps in your forked repository:

1. Navigate to the **Settings** tab
1. Click on **Pages** in the left navigation
1. In the **GitHub Pages** section, select **GitHub Actions** as the Source
1. Navigate to the **Actions** tab
1. If this is your first time running GitHub Actions in the repo, click on the green button that says **I understand my workflows, go ahead and enable them**. This will enable the GitHub Actions workflow to build and deploy your changes to GitHub Pages.
1. Click on the **Deploy to GitHub Pages** in the left navigation
1. Click the **Run workflow** button. This will trigger the workflow to build and deploy your changes to GitHub Pages.

Once the workflow has completed, you can access your site at `https://<your-github-username>.github.io/gbb-blog/`.

:::warning

GitHub Pages in your forked repository will only build and deploy when changes are pushed to the main branch of your fork. So if you are working on a feature branch, you will need to merge your changes into the main branch to see them deployed to GitHub Pages.

:::

That's it! Thank you for your contribution!