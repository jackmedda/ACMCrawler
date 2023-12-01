# ACMCrawler

Simple crawler of ACM proceedings of various conferences based on Selenium.
Selenium should be required because paper results are lazily loaded. The conferences are identified
by a concept ID, which can be found in the url of the corresponding conference proceedings
webpage.

Concept (Conferences) IDs can be added in the [concept_ids.json](concept_ids.json) file
using the name or acronym of the conference as the key.

[query_templates.json](query_templates.json) contains the base query or parts to add
to the base query for the webpage url. ACM supports advanced queries like searching for
specific terms in specific fields (e.g., title="Neural*"). This repository provides
only the base one, which queries a certain string in all the fields.

Example of command:
```
python main.py -q "graph* OR gnn* OR rank* OR knowledge* OR topolog* OR social net* OR recomm* OR retriev*" -yi 2020 2023
```

- `--queries, -q` is used to specify the query to search. It supports any formatting used in the
ACM textarea (e.g., OR, AND)
- `--concepts_ids, -cid` it can take "all" or a list of conference keys in the [concept_ids.json](concept_ids.json) file
- `--year_interval, -yi,` takes two arguments as the two extremes of a year interval
- `--query_template, -qt` the key for the query template to use from the corresponding json file
- `--page_info, -pi` takes two arguments, the page size (papers retrieved for each page)
and starting page from which papers should be scraped
- `--authors_info_file, -aif` the output file including the info of unique authors, identified
by the ACM profile ID