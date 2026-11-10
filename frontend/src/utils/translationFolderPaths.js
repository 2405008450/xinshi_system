// 同一次目录提取的母订单路径、隐藏网络路径字段和项目文件草稿必须使用同一根路径。
export function applyFolderRootPath(form,rootPath){
  const root=String(rootPath||'').trim()
  if(!root)return
  Object.assign(form,{originalStoragePath:root,networkFilePath:root,
    filePathDraft:{...(form.filePathDraft||{}),storage_path:root},folderRootPathVersion:1})
}

// 只修复旧格式未保存目录草稿一次；之后保留用户独立修改的原文路径。
export function restoreFolderRootPath(form){
  if(form.pendingFolderImport?.rootPath&&!form.folderRootPathVersion)applyFolderRootPath(form,form.pendingFolderImport.rootPath)
}
