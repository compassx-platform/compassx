/** Preamble that points a notebook kernel at that notebook's MLflow experiment. */

export function notebookExperimentName(notebookPath: string): string {
  const clean = notebookPath.replace(/\\/g, '/').replace(/^\/+/, '');
  return clean ? `/${clean}` : '';
}

export function notebookMlflowPreamble(
  notebookPath: string,
  notebookId = '',
  trackingUri = '',
): string {
  const experimentName = notebookExperimentName(notebookPath);
  if (!experimentName) return '';
  const notebookFile = experimentName.replace(/^\/+/, '');
  const tracking = trackingUri
    ? `os.environ.setdefault('MLFLOW_TRACKING_URI', ${JSON.stringify(trackingUri)})\n`
    : '';
  return [
    'import os',
    `os.environ['COMPASSX_NOTEBOOK_PATH'] = ${JSON.stringify(notebookFile)}`,
    "os.environ['NOTEBOOK_PATH'] = os.environ['COMPASSX_NOTEBOOK_PATH']",
    `os.environ['NOTEBOOK_ID'] = ${JSON.stringify(notebookId)}`,
    `os.environ['MLFLOW_EXPERIMENT_NAME'] = ${JSON.stringify(experimentName)}`,
    tracking.trimEnd(),
    'try:',
    '    import mlflow',
    "    if os.environ.get('MLFLOW_TRACKING_URI'):",
    "        mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])",
    "    _exp = os.environ['MLFLOW_EXPERIMENT_NAME']",
    "    _bound = os.environ.get('COMPASSX_BOUND_EXPERIMENT')",
    '    _current = None',
    '    try:',
    '        from mlflow.tracking.fluent import _get_experiment_id',
    '        _eid = _get_experiment_id()',
    '        if _eid:',
    '            _found = mlflow.get_experiment(_eid)',
    "            _current = getattr(_found, 'name', None)",
    '            if not isinstance(_current, str):',
    '                _current = None',
    '    except Exception:',
    '        _current = None',
    "    if not _bound or _current in (None, 'Default', _bound):",
    '        if not mlflow.get_experiment_by_name(_exp):',
    '            try:',
    '                mlflow.create_experiment(_exp)',
    '            except Exception:',
    '                pass',
    '        mlflow.set_experiment(_exp)',
    "        os.environ['COMPASSX_BOUND_EXPERIMENT'] = _exp",
    "        if os.environ.get('COMPASSX_MLFLOW_AUTOLOG', 'true').lower() in ('true', '1', 'yes') and os.environ.get('COMPASSX_MLFLOW_AUTOLOG_DONE') != '1':",
    '            try:',
    '                mlflow.autolog(log_models=True, silent=True)',
    '            except Exception:',
    '                pass',
    "            os.environ['COMPASSX_MLFLOW_AUTOLOG_DONE'] = '1'",
    'except Exception:',
    '    pass',
  ].filter(Boolean).join('\n');
}
