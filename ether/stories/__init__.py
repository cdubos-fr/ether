"""The stories domain: markdown-backed sagas/one-shots -> tomes -> acts -> chapters.

Built the same way `ether.univers` is: markdown files under a project's
`stories/` folder are the source of truth; the DB tables in `index_models`
are a disposable, rebuildable cache (see that module's docstring). A story
node (a saga/one-shot/tome/act's `_index.md`, or a chapter file) shares the
same generic fiche shape univers already uses (`ether.stories.schema`), so
tags/aliases/`related` all mean what they already mean elsewhere in ether.

See `ether.project` for the folder-shape rules that make a story a "saga" or
a "one-shot", and the module docstring on `ether.sequencer` for what this
replaces there.
"""
