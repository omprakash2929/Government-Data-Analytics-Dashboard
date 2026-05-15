import os
import json
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify
import plotly
import plotly.express as px
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

global_df = None
global_columns = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    global global_df, global_columns
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            if filename.endswith('.csv'):
                global_df = pd.read_csv(filepath)
            elif filename.endswith(('.xls', '.xlsx')):
                global_df = pd.read_excel(filepath)
            elif filename.endswith('.json'):
                try:
                    global_df = pd.read_json(filepath, orient='records')
                except Exception:
                    global_df = pd.read_json(filepath)
            else:
                return jsonify({'error': 'Invalid file format. Please upload CSV, Excel, or JSON.'}), 400
                
            global_df = global_df.fillna("N/A")
            global_columns = list(global_df.columns)
            return jsonify({'message': 'File uploaded successfully', 'columns': global_columns})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['POST'])
def get_data():
    global global_df, global_columns
    if global_df is None:
        return jsonify({'error': 'No data uploaded yet'}), 400
        
    req_data = request.json or {}
    search_term = req_data.get('search', '').lower()
    search_col = req_data.get('search_col', 'all')
    limit = req_data.get('limit', 100)
    
    chart_x = req_data.get('chart_x')
    chart_y = req_data.get('chart_y')
    chart_type = req_data.get('chart_type')
    
    df_filtered = global_df.copy()
    
    if search_term:
        if search_col == 'all':
            mask = df_filtered.astype(str).apply(lambda x: x.str.lower().str.contains(search_term)).any(axis=1)
            df_filtered = df_filtered[mask]
        elif search_col in df_filtered.columns:
            mask = df_filtered[search_col].astype(str).str.lower().str.contains(search_term)
            df_filtered = df_filtered[mask]
        
    # Exclude "N/A" for numeric calculations by replacing with NaN
    df_numeric = df_filtered.replace("N/A", np.nan)
    
    summary = {
        'total_rows': int(len(global_df)),
        'filtered_rows': int(len(df_filtered)),
        'total_columns': int(len(df_filtered.columns)),
        'missing_values': int(df_numeric.isna().sum().sum()),
        'duplicates': int(df_filtered.duplicated().sum())
    }
        
    charts = []
    
    for col in df_numeric.columns:
        if df_numeric[col].dtype == 'object':
            try:
                df_numeric[col] = pd.to_numeric(df_numeric[col])
            except:
                pass

    # Custom Chart
    if chart_x and chart_y and chart_type and chart_x in df_numeric.columns and chart_y in df_numeric.columns:
        try:
            custom_title = f"Custom {chart_type.capitalize()} Chart: {chart_y} by {chart_x}"
            if chart_type == 'bar':
                agg_df = df_numeric.groupby(chart_x)[chart_y].sum().reset_index().sort_values(chart_y, ascending=False).head(20)
                fig_custom = px.bar(agg_df, x=chart_x, y=chart_y, title=custom_title, template='plotly_dark', color=chart_y, color_continuous_scale=px.colors.sequential.Sunset, text_auto='.2s')
            elif chart_type == 'line':
                agg_df = df_numeric.groupby(chart_x)[chart_y].sum().reset_index().sort_values(chart_x)
                fig_custom = px.line(agg_df, x=chart_x, y=chart_y, title=custom_title, template='plotly_dark', markers=True)
                fig_custom.update_traces(line=dict(width=3, color='#3b82f6'), marker=dict(size=8, color='#60a5fa'))
            elif chart_type == 'pie':
                agg_df = df_numeric.groupby(chart_x)[chart_y].sum().reset_index().sort_values(chart_y, ascending=False).head(10)
                fig_custom = px.pie(agg_df, names=chart_x, values=chart_y, title=custom_title, template='plotly_dark', hole=0.35, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_custom.update_traces(textinfo='percent+label', pull=[0.05]*len(agg_df))
            elif chart_type == 'scatter':
                # Map size to y-value to create a bubble chart effect
                # fillna(0) and map negative to 0 for size
                scatter_df = df_numeric.head(1000).copy()
                scatter_df['size'] = scatter_df[chart_y].fillna(0).apply(lambda x: max(x, 0))
                fig_custom = px.scatter(scatter_df, x=chart_x, y=chart_y, title=custom_title, template='plotly_dark', color=chart_x, size='size', opacity=0.8, color_discrete_sequence=px.colors.qualitative.Vivid, hover_data=[chart_x, chart_y])
            
            if 'fig_custom' in locals():
                fig_custom.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, zeroline=False),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False)
                )
                charts.append(json.loads(fig_custom.to_json()))
        except Exception as e:
            print("Error generating custom chart:", e)

    # Auto Charts
    date_cols = df_filtered.select_dtypes(include=['datetime', 'object']).columns
    date_col = next((col for col in date_cols if any(kw in col.lower() for kw in ['date', 'month', 'year', 'time'])), None)
    
    cat_cols = df_filtered.select_dtypes(include=['object', 'category']).columns
    cat_col = next((col for col in cat_cols if df_filtered[col].nunique() < 20 and col != date_col), None)
    
    num_cols = df_numeric.select_dtypes(include=['number']).columns
    num_col = num_cols[0] if len(num_cols) > 0 else None

    # 1. Sum of numeric columns
    num_cols_for_sum = [c for c in num_cols if 'year' not in c.lower() and 'id' not in c.lower()]
    if len(num_cols_for_sum) > 1:
        try:
            sums = df_numeric[num_cols_for_sum].sum().reset_index()
            sums.columns = ['Category', 'Total']
            sums = sums.sort_values('Total', ascending=False).head(15)
            fig_sums = px.bar(sums, x='Category', y='Total', title='Top 15 Categories by Volume', template='plotly_dark', color='Total', color_continuous_scale=px.colors.sequential.Plasma, text_auto='.2s')
            fig_sums.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'))
            charts.append(json.loads(fig_sums.to_json()))
        except Exception:
            pass

    # 2. Line Chart for trends
    if date_col and num_col:
        try:
            trend_df = df_numeric.groupby(date_col)[num_col].sum().reset_index()
            trend_df = trend_df.sort_values(date_col)
            fig1 = px.line(trend_df, x=date_col, y=num_col, title=f'{num_col} Trend over {date_col}', template='plotly_dark', markers=True)
            fig1.update_traces(line=dict(width=3, color='#10b981'), marker=dict(size=8, color='#34d399'))
            fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'))
            charts.append(json.loads(fig1.to_json()))
        except Exception:
            pass

    # 3. Bar/Pie Chart for categories
    if cat_col:
        try:
            counts = df_filtered[cat_col].value_counts().reset_index()
            counts.columns = [cat_col, 'Count']
            counts = counts.head(10)
            fig2 = px.bar(counts, x=cat_col, y='Count', title=f'Distribution of {cat_col} (Top 10)', template='plotly_dark', color='Count', color_continuous_scale=px.colors.sequential.Tealgrn, text_auto=True)
            fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'))
            charts.append(json.loads(fig2.to_json()))
            
            fig3 = px.pie(counts, names=cat_col, values='Count', title=f'{cat_col} Proportion', template='plotly_dark', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            fig3.update_traces(textinfo='percent+label', pull=[0.05]*len(counts))
            fig3.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            charts.append(json.loads(fig3.to_json()))
        except Exception:
            pass
            
    # 4. Histogram
    if num_col and len(df_numeric[num_col].unique()) > 5:
        try:
            fig4 = px.histogram(df_numeric, x=num_col, title=f'Distribution of {num_col}', template='plotly_dark', color_discrete_sequence=['#8b5cf6'], nbins=30)
            fig4.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'))
            charts.append(json.loads(fig4.to_json()))
        except Exception:
            pass

    if limit != 'all':
        try:
            limit = int(limit)
            table_data = df_filtered.head(limit).to_dict(orient='records')
        except ValueError:
            table_data = df_filtered.head(100).to_dict(orient='records')
    else:
        table_data = df_filtered.to_dict(orient='records')
    
    return jsonify({
        'summary': summary,
        'charts': charts,
        'table_data': table_data,
        'columns': global_columns
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
