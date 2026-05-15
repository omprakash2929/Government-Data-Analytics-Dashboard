document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const statusMsg = document.getElementById('upload-status');
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const chartsContainer = document.getElementById('charts-container');
    const tableContainer = document.getElementById('table-container');
    const rowCountEl = document.getElementById('row-count');
    const exportPdfBtn = document.getElementById('export-pdf-btn');
    
    const limitSelect = document.getElementById('row-limit-select');
    const filterSelect = document.getElementById('filter-column-select');
    
    // Custom Chart Elements
    const chartXCol = document.getElementById('chart-x-col');
    const chartYCol = document.getElementById('chart-y-col');
    const chartType = document.getElementById('chart-type');
    const generateChartBtn = document.getElementById('generate-chart-btn');

    const summaryContainer = document.getElementById('summary-container');
    const statCols = document.getElementById('stat-cols');
    const statRows = document.getElementById('stat-rows');
    const statMissing = document.getElementById('stat-missing');
    const statDupes = document.getElementById('stat-dupes');

    let currentSearchTerm = '';

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        uploadBtn.textContent = 'Uploading...';
        uploadBtn.disabled = true;
        statusMsg.textContent = '';
        statusMsg.className = 'status-msg';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (response.ok) {
                statusMsg.textContent = 'File uploaded successfully!';
                statusMsg.classList.add('success');
                currentSearchTerm = '';
                searchInput.value = '';
                
                if (data.columns) {
                    populateDropdowns(data.columns);
                }
                
                fetchAndRenderData();
            } else {
                statusMsg.textContent = data.error || 'Upload failed.';
                statusMsg.classList.add('error');
            }
        } catch (error) {
            statusMsg.textContent = 'Network error during upload.';
            statusMsg.classList.add('error');
        } finally {
            uploadBtn.textContent = 'Upload & Analyze';
            uploadBtn.disabled = false;
        }
    });

    searchBtn.addEventListener('click', () => {
        currentSearchTerm = searchInput.value;
        fetchAndRenderData();
    });

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            currentSearchTerm = searchInput.value;
            fetchAndRenderData();
        }
    });

    limitSelect.addEventListener('change', () => {
        fetchAndRenderData();
    });

    generateChartBtn.addEventListener('click', () => {
        if(!chartXCol.value || !chartYCol.value) {
            alert("Please select both X and Y axis columns for the custom chart.");
            return;
        }
        fetchAndRenderData();
    });

    exportPdfBtn.addEventListener('click', () => {
        const element = document.getElementById('dashboard-content');
        const opt = {
            margin:       0.3,
            filename:     'analytics_dashboard_report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true },
            jsPDF:        { unit: 'in', format: 'a4', orientation: 'landscape' }
        };
        
        element.classList.add('exporting-pdf');
        html2pdf().set(opt).from(element).save().then(() => {
            element.classList.remove('exporting-pdf');
        });
    });

    function populateDropdowns(columns) {
        const curFilter = filterSelect.value;
        const curX = chartXCol.value;
        const curY = chartYCol.value;

        filterSelect.innerHTML = '<option value="all">All Columns</option>';
        chartXCol.innerHTML = '<option value="">X-Axis (Category/Date)</option>';
        chartYCol.innerHTML = '<option value="">Y-Axis (Numeric value)</option>';
        
        columns.forEach(col => {
            filterSelect.innerHTML += `<option value="${col}">${col}</option>`;
            chartXCol.innerHTML += `<option value="${col}">${col}</option>`;
            chartYCol.innerHTML += `<option value="${col}">${col}</option>`;
        });

        if (curFilter && curFilter !== 'all' && columns.includes(curFilter)) filterSelect.value = curFilter;
        if (curX && columns.includes(curX)) chartXCol.value = curX;
        if (curY && columns.includes(curY)) chartYCol.value = curY;
    }

    async function fetchAndRenderData() {
        chartsContainer.innerHTML = '<div class="empty-state glass-panel" style="grid-column: 1 / -1;"><p>Analyzing data & generating insights...</p></div>';
        
        const limit = limitSelect.value;
        const filterCol = filterSelect.value;
        const chartX = chartXCol.value;
        const chartY = chartYCol.value;
        const type = chartType.value;

        try {
            const response = await fetch('/api/data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    search: currentSearchTerm,
                    search_col: filterCol,
                    limit: limit,
                    chart_x: chartX,
                    chart_y: chartY,
                    chart_type: type
                })
            });
            const data = await response.json();

            if (response.ok) {
                summaryContainer.style.display = 'grid';
                statCols.textContent = data.summary.total_columns.toLocaleString();
                statRows.textContent = data.summary.total_rows.toLocaleString();
                statMissing.textContent = data.summary.missing_values.toLocaleString();
                statDupes.textContent = data.summary.duplicates.toLocaleString();

                rowCountEl.textContent = data.summary.filtered_rows.toLocaleString();
                
                if (data.columns && filterSelect.options.length <= 1) {
                    populateDropdowns(data.columns);
                }

                renderCharts(data.charts);
                renderTable(data.table_data);
            } else {
                chartsContainer.innerHTML = `<div class="empty-state glass-panel" style="grid-column: 1 / -1;"><p class="error">${data.error || 'Failed to generate charts.'}</p></div>`;
            }
        } catch (error) {
            chartsContainer.innerHTML = `<div class="empty-state glass-panel" style="grid-column: 1 / -1;"><p class="error">Error connecting to server.</p></div>`;
        }
    }

    function renderCharts(charts) {
        chartsContainer.innerHTML = '';
        if (!charts || charts.length === 0) {
            chartsContainer.innerHTML = '<div class="empty-state glass-panel" style="grid-column: 1 / -1;"><p>No clear patterns found to auto-generate charts for this data view.</p></div>';
            return;
        }

        charts.forEach((chartJson, index) => {
            const card = document.createElement('div');
            card.className = 'card glass-panel chart-container';
            
            // First chart wide
            if (index === 0 && charts.length >= 2) {
                card.style.gridColumn = '1 / -1'; 
            }
            
            // INCREASED HEIGHT so charts/labels fit properly
            card.style.height = '550px'; 
            
            const chartDiv = document.createElement('div');
            chartDiv.id = `plotly-chart-${index}`;
            chartDiv.style.width = '100%';
            chartDiv.style.height = '100%';
            
            card.appendChild(chartDiv);
            chartsContainer.appendChild(card);

            chartJson.layout.paper_bgcolor = 'rgba(0,0,0,0)';
            chartJson.layout.plot_bgcolor = 'rgba(0,0,0,0)';
            chartJson.layout.font = { family: 'Inter, sans-serif', color: '#f8fafc' };
            
            // ADD MARGIN so X-axis labels aren't cut off when they rotate
            chartJson.layout.margin = { l: 60, r: 20, t: 60, b: 160 };
            chartJson.layout.autosize = true;

            Plotly.newPlot(chartDiv.id, chartJson.data, chartJson.layout, { responsive: true });
        });
    }

    function renderTable(tableData) {
        tableContainer.style.display = 'block';
        const thead = document.getElementById('data-table-head');
        const tbody = document.getElementById('data-table-body');
        
        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (!tableData || tableData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="100%" style="text-align: center;">No data matches your filter.</td></tr>';
            return;
        }

        const columns = Object.keys(tableData[0]);
        const headerRow = document.createElement('tr');
        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        tableData.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(col => {
                const td = document.createElement('td');
                td.textContent = row[col];
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }
});
