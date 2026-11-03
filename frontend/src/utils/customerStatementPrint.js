// 打印使用独立文档，避免带出弹窗、筛选栏及全局应用样式。
export const statementPrintStyles=`
@page{size:A4 landscape;margin:14mm}body{font-family:'Microsoft YaHei',sans-serif;color:#222;margin:0;background:#fff}
.statement-paper{padding:0}.statement-paper h2,.statement-paper h3{text-align:center;margin:0 0 12px}.statement-paper h2{font-size:22px}.statement-paper h3{font-size:20px}
.statement-meta{display:flex;justify-content:space-between;margin:20px 0 12px}.statement-table-wrap{position:relative}
.statement-table{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed}.statement-table th,.statement-table td{border:1px solid #777;padding:8px 5px;text-align:center;overflow-wrap:anywhere;white-space:pre-wrap}
.statement-table th:nth-child(2){width:21%}.statement-table th:nth-child(4){width:18%}.statement-table th:nth-child(5){width:16%}.statement-table thead{display:table-header-group}.statement-table tfoot{display:table-row-group;font-weight:bold}.statement-table tfoot td{height:56px}.statement-total-label{text-align:right!important;padding-right:20px!important}
.statement-stamp{position:absolute;z-index:2;width:135px;height:135px;object-fit:contain;left:45%;bottom:-18px;opacity:.85;mix-blend-mode:multiply;print-color-adjust:exact;-webkit-print-color-adjust:exact}
.statement-account{margin-top:32px;break-inside:avoid}.statement-account h4{font-size:15px;margin:0 0 14px}.statement-account p{margin:7px 0;font-size:13px}.statement-incomplete{font-size:11px;color:#9b3c15}tr{break-inside:avoid}
`
