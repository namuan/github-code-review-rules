/* GitHub PR Rules Analyzer - Dashboard JavaScript */

document.addEventListener("DOMContentLoaded", () => {
      // Initialize dashboard
      initDashboard();
});

function initDashboard() {
      // Initialize charts
      initCategoriesChart();
      initSeveritiesChart();

      // Initialize rules list
      initRulesList();

      // Initialize repositories list
      initRepositoriesList();

      // Initialize sync controls
      initSyncControls();

      // Initialize event listeners
      initEventListeners();
}

function initCategoriesChart() {
      const ctx = document.getElementById("categories-chart").getContext("2d");
      new Chart(ctx, {
            type: "pie",
            data: {
                  labels: [],
                  datasets: [
                        {
                              data: [],
                              backgroundColor: [
                                    "#667eea",
                                    "#764ba2",
                                    "#f093fb",
                                    "#f5576c",
                                    "#4facfe",
                                    "#00f2fe",
                                    "#43e97b",
                                    "#38f9d7",
                              ],
                        },
                  ],
            },
            options: {
                  plugins: {
                        tooltip: {
                              callbacks: {
                                    label: (context) => {
                                          var label = context.label || "";
                                          if (label) {
                                                label += ": ";
                                          }
                                          if (context.parsed !== null) {
                                                label += new Intl.NumberFormat("en-US", {
                                                      style: "percent",
                                                }).format(context.parsed);
                                          }
                                          return label;
                                    },
                              },
                        },
                  },
            },
      });
}

function initSeveritiesChart() {
      const ctx = document.getElementById("severities-chart").getContext("2d");
      new Chart(ctx, {
            type: "bar",
            data: {
                  labels: [],
                  datasets: [
                        {
                              label: "Rule Count",
                              data: [],
                              backgroundColor: "rgba(9, 105, 218, 0.5)",
                              borderColor: "rgba(9, 105, 218, 1)",
                              borderWidth: 1,
                        },
                  ],
            },
            options: {
                  scales: {
                        y: {
                              beginAtZero: true,
                              stepSize: 1,
                        },
                  },
            },
      });
}

function initRulesList() {
      // Fetch rules from API
      fetchRulesList();
}

function fetchRulesList() {
      const searchQuery = document.getElementById("rules-search").value;
      const categoryFilter = document.getElementById("category-filter").value;
      const severityFilter = document.getElementById("severity-filter").value;
      const repositoryFilter = document.getElementById("repository-filter").value;

      // Build API URL
      const apiUrl = `/api/v1/rules/search?query=${encodeURIComponent(searchQuery)}&category=${encodeURIComponent(
            categoryFilter,
      )}&severity=${encodeURIComponent(severityFilter)}&repository=${encodeURIComponent(repositoryFilter)}`;

      // Fetch data
      fetch(apiUrl)
            .then((response) => response.json())
            .then((data) => {
                  updateRulesList(data);
            })
            .catch((error) => {
                  showErrorToast("Error fetching rules list");
            });
}

function updateRulesList(data) {
      const rulesListElement = document.getElementById("rules-list");
      rulesListElement.innerHTML = "";

      data.rules.forEach((rule) => {
            const ruleElement = document.createElement("div");
            ruleElement.classList.add("rule-item");
            ruleElement.innerHTML = `
            <div class="rule-header">
                <h3 class="rule-text">${rule.rule_text}</h3>
                <div class="rule-meta">
                    <span class="category rule-tag category">${rule.rule_category}</span>
                    <span class="severity rule-tag severity">${rule.rule_severity}</span>
                </div>
            </div>
            <div class="rule-details">
                <p>Confidence: ${rule.confidence_score * 100}%</p>
                <p>Created: ${new Date(rule.created_at).toLocaleString()}</p>
            </div>
        `;
            rulesListElement.appendChild(ruleElement);
      });

      updatePagination(data);
}

function updatePagination(data) {
      const paginationElement = document.getElementById("rules-pagination");
      paginationElement.innerHTML = "";

      const pageInfo = document.createElement("div");
      pageInfo.classList.add("page-info");
      pageInfo.textContent = `Showing ${data.skip + 1} to ${data.skip + data.limit} of ${data.total} rules`;
      paginationElement.appendChild(pageInfo);

      // Add previous button
      const prevButton = document.createElement("button");
      prevButton.classList.add("btn", "btn-secondary");
      prevButton.textContent = "Previous";
      prevButton.disabled = data.skip === 0;
      prevButton.addEventListener("click", () => {
            fetchRulesList(data);
      });
      paginationElement.appendChild(prevButton);

      // Add next button
      const nextButton = document.createElement("button");
      nextButton.classList.add("btn", "btn-secondary");
      nextButton.textContent = "Next";
      nextButton.disabled = data.skip >= data.total - data.limit;
      nextButton.addEventListener("click", () => {
            fetchRulesList(data);
      });
      paginationElement.appendChild(nextButton);
}

function initRepositoriesList() {
      // Fetch repositories from API
      fetchRepositoriesList();
}

function fetchRepositoriesList() {
      fetch("/api/v1/repositories")
            .then((response) => response.json())
            .then((data) => {
                  updateRepositoriesList(data);
            })
            .catch((error) => {
                  showErrorToast("Error fetching repositories list");
            });
}

function updateRepositoriesList(data) {
      const repositoriesListElement = document.getElementById("repositories-list");
      repositoriesListElement.innerHTML = "";

      data.repositories.forEach((repo) => {
            const repoElement = document.createElement("div");
            repoElement.classList.add("repository-item");
            repoElement.innerHTML = `
            <div class="repository-info">
                <h3 class="repository-name">${repo.name}</h3>
                <div class="repository-meta">
                    <p>Owner: ${repo.owner_login}</p>
                    <p>URL: ${repo.html_url}</p>
                </div>
            </div>
            <div class="repository-actions">
                <button class="btn btn-primary sync-repo-btn" data-repo-id="${repo.id}">Sync</button>
                <button class="btn btn-danger delete-repo-btn" data-repo-id="${repo.id}">Delete</button>
            </div>
        `;
            repositoriesListElement.appendChild(repoElement);
      });

      // Add event listeners for sync buttons
      document.querySelectorAll(".sync-repo-btn").forEach((button) => {
            button.addEventListener("click", (e) => {
                  const repoId = e.target.getAttribute("data-repo-id");
                  syncRepository(repoId);
            });
      });

      // Add event listeners for delete buttons
      document.querySelectorAll(".delete-repo-btn").forEach((button) => {
            button.addEventListener("click", (e) => {
                  const repoId = e.target.getAttribute("data-repo-id");
                  deleteRepository(repoId);
            });
      });
}

function initSyncControls() {
      // Initialize sync controls
      updateSyncStatus();
}

function updateSyncStatus() {
      fetch("/api/v1/sync/status")
            .then((response) => response.json())
            .then((data) => {
                  updateSyncStatusUI(data);
            })
            .catch((error) => {
                  showErrorToast("Error fetching sync status");
            });
}

function updateSyncStatusUI(data) {
      const processedCountElement = document.getElementById("processed-count");
      const errorCountElement = document.getElementById("error-count");
      const queueSizeElement = document.getElementById("queue-size");
      const workerCountElement = document.getElementById("worker-count");

      processedCountElement.textContent = data.processing_stats.processed_count;
      errorCountElement.textContent = data.processing_stats.error_count;
      queueSizeElement.textContent = data.processing_stats.queue_size;
      workerCountElement.textContent = data.processing_stats.worker_count;
}

function initEventListeners() {
      // Add repository form submission
      document.getElementById("add-repo-btn").addEventListener("click", () => {
            const ownerInput = document.getElementById("repo-owner");
            const nameInput = document.getElementById("repo-name");

            if (ownerInput.value.trim() === "" || nameInput.value.trim() === "") {
                  showErrorToast("Please enter repository owner and name");
                  return;
            }

            // Add repository to API
            fetch("/api/v1/repositories", {
                  method: "POST",
                  headers: {
                        "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                        owner: ownerInput.value.trim(),
                        name: nameInput.value.trim(),
                  }),
            })
                  .then((response) => {
                        // Store the response status before converting to JSON
                        const isOk = response.ok;
                        return response.json().then((data) => ({ data, isOk }));
                  })
                  .then(({ data, isOk }) => {
                        if (isOk) {
                              showSuccessToast("Repository added successfully");
                              ownerInput.value = "";
                              nameInput.value = "";
                              fetchRepositoriesList();
                        } else {
                              showErrorToast("Error adding repository");
                        }
                  })
                  .catch((error) => {
                        showErrorToast("Error adding repository");
                  });
      });

      // Sync all repositories
      document.getElementById("sync-all-btn").addEventListener("click", () => {
            fetch("/api/v1/sync")
                  .then((response) => {
                        // Store the response status before converting to JSON
                        const isOk = response.ok;
                        return response.json().then((data) => ({ data, isOk }));
                  })
                  .then(({ data, isOk }) => {
                        if (isOk) {
                              showSuccessToast("Repository sync started");
                              updateSyncStatus();
                        } else {
                              showErrorToast("Error starting sync");
                        }
                  })
                  .catch((error) => {
                        showErrorToast("Error starting sync");
                  });
      });

      // Sync selected repositories
      document.getElementById("sync-selected-btn").addEventListener("click", () => {
            // TODO: Implement sync selected repositories
            showErrorToast("Sync selected repositories not implemented");
      });

      // Stop sync
      document.getElementById("stop-sync-btn").addEventListener("click", () => {
            // TODO: Implement stop sync
            showErrorToast("Stop sync not implemented");
      });

      // Page navigation
      document.querySelectorAll(".nav-link[data-page]").forEach((link) => {
            link.addEventListener("click", (e) => {
                  e.preventDefault();
                  const page = link.getAttribute("data-page");
                  switchPage(page);
            });
      });

      // View all rules link
      document.querySelectorAll(".view-all[data-page]").forEach((link) => {
            link.addEventListener("click", (e) => {
                  e.preventDefault();
                  switchPage(link.getAttribute("data-page"));
            });
      });
}

function showErrorToast(message) {
      const toastElement = document.getElementById("error-toast");
      toastElement.classList.add("show");
      toastElement.querySelector("#error-message").textContent = message;
      setTimeout(() => {
            toastElement.classList.remove("show");
      }, 5000);
}

function showSuccessToast(message) {
      const toastElement = document.getElementById("success-toast");
      toastElement.classList.add("show");
      toastElement.querySelector("#success-message").textContent = message;
      setTimeout(() => {
            toastElement.classList.remove("show");
      }, 5000);
}

function toggleLoadingOverlay(show) {
      const overlayElement = document.getElementById("loading-overlay");
      overlayElement.classList.toggle("active", show);
}

function switchPage(pageName) {
      // Hide all pages
      document.querySelectorAll(".page").forEach((page) => {
            page.classList.remove("active");
      });

      // Remove active class from all nav links
      document.querySelectorAll(".nav-link").forEach((link) => {
            link.classList.remove("active");
      });

      // Show the selected page
      const targetPage = document.getElementById(`${pageName}-page`);
      if (targetPage) {
            targetPage.classList.add("active");

            // Add active class to the corresponding nav link
            const activeLink = document.querySelector(`.nav-link[data-page="${pageName}"]`);
            if (activeLink) {
                  activeLink.classList.add("active");
            }

            // Refresh data for the page if needed
            if (pageName === "repositories") {
                  fetchRepositoriesList();
            } else if (pageName === "rules") {
                  fetchRulesList();
            } else if (pageName === "sync") {
                  updateSyncStatus();
            }
      }
}

function syncRepository(repoId) {
      // Show loading indicator
      toggleLoadingOverlay(true);

      fetch(`/api/v1/sync/${repoId}`, {
            method: "POST",
            headers: {
                  "Content-Type": "application/json",
            },
      })
            .then((response) => {
                  toggleLoadingOverlay(false);
                  if (response.ok) {
                        showSuccessToast("Repository sync started successfully");
                        // Update sync status
                        updateSyncStatus();
                  } else {
                        showErrorToast("Error starting repository sync");
                  }
            })
            .catch((error) => {
                  toggleLoadingOverlay(false);
                  showErrorToast("Error starting repository sync");
            });
}

function deleteRepository(repoId) {
      if (!confirm("Are you sure you want to delete this repository?")) {
            return;
      }

      toggleLoadingOverlay(true);

      fetch(`/api/v1/repositories/${repoId}`, {
            method: "DELETE",
            headers: {
                  "Content-Type": "application/json",
            },
      })
            .then((response) => {
                  toggleLoadingOverlay(false);
                  if (response.ok) {
                        showSuccessToast("Repository deleted successfully");
                        fetchRepositoriesList();
                  } else {
                        showErrorToast("Error deleting repository");
                  }
            })
            .catch((error) => {
                  toggleLoadingOverlay(false);
                  showErrorToast("Error deleting repository");
            });
}
