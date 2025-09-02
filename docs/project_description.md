A system that collects, processes, and analyzes GitHub pull request (PR) comments to generate coding rules. The system will be used by to improve code quality and enforce coding standards automatically.

Data Collector:

Connect to GitHub using the API and go through all the closed Pull Requests.

For each closed pull request:

- It should collect review data

* Context around the review comments
* Surrounding Code Snippet
* Date time
* Comment Thread

Save it in database

--

Data Analysis:

The next phase is to extract rules out of each entry

For each entry

- Send all data to LLM and prompt LLM to extract an application rule

- Save the rule in the database along with the other review details.

---

Data Presentation

Present the data in the database in a user friendly way using a Web UI.

A simple UI is sufficient without any authentication
