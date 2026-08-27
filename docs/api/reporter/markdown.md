---
title: Markdown Reporter
hide:
  - tags
tags:
  - API
  - Reports
  - Python
---

<!--
  ~ Copyright (c) 2023-2026 Arista Networks, Inc.
  ~ Use of this source code is governed by the Apache License 2.0
  ~ that can be found in the LICENSE file.
  -->

::: anta.reporter.md_reporter.MDReportBase
    options:
        inherited_members:
          - ICON
          - format_snake_case_to_title_case
          - format_status
          - format_timedelta
          - format_value
          - generate_heading_name
          - generate_rows
          - generate_section
          - generate_table_heading
          - safe_markdown
          - write_heading
          - write_table

::: anta.reporter.md_reporter
    options:
        filters: ["!^_", "!^MDReportBase$"]
        show_root_heading: false
        show_root_toc_entry: false
