# Troubleshooting

## Assets Still Appear With No Paths Configured

Current intended behavior:

- if no library roots are enabled, cached assets are cleared
- removing the last root clears the runtime index
- restarting Blender with no roots configured shows an empty browser

## New Category Or Sub-category Will Not Add

Check that:

- you typed the new value into the `Name` field
- for sub-categories, the parent category is selected first
- you clicked `Add`, not `Update`

## Import Fails

Common causes:

- the currently open `.blend` is the same file as the source asset
- metadata target names do not match the source file
- the source file changed and needs a rescan

## Preview Is Missing Or Outdated

Try:

1. confirming a preview file exists or metadata points to one
2. using `Regenerate Thumbnail`
3. rescanning the library
