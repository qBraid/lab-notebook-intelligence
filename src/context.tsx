import React, { useEffect, useState } from 'react';
import {
  VscArrowLeft,
  VscFile,
  VscFolder,
  VscArrowRight
} from 'react-icons/vsc';

import { ContentsManager } from '@jupyterlab/services';

const contentsManager = new ContentsManager();

export function FileBrowserDropdown(props: {
  onFilesSelected: (filePaths: string[]) => void;
  onCancelSelection: () => void;
}) {
  const [currentPath, setCurrentPath] = useState<any>(null);
  const [parentPaths, setParentPaths] = useState<any[]>([]); // Stack of parent paths
  const [files, setFiles] = useState<any[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Fetch files when the component mounts or the path changes
    const fetchFiles = async (path: string = '') => {
      const response = await contentsManager.get(path);
      setFiles(response.content); // Returns an array of files and directories
    };
    fetchFiles(currentPath?.path);
  }, [currentPath]);

  const handleFileClick = (file: any) => {
    if (file.type === 'directory') {
      // Navigate into the directory
      setParentPaths([...parentPaths, currentPath]); // Append currentPath to parentPaths
      setCurrentPath(file); // Set the clicked directory as the current path
    } else {
      // Toggle file selection
      const updatedSelectedFiles = new Set(selectedFiles);
      if (updatedSelectedFiles.has(file.path)) {
        updatedSelectedFiles.delete(file.path);
      } else {
        updatedSelectedFiles.add(file.path);
      }
      setSelectedFiles(updatedSelectedFiles);
    }
  };

  const handleBackClick = () => {
    if (parentPaths.length > 0) {
      const newParentPaths = [...parentPaths];
      const lastParentPath = newParentPaths.pop(); // Remove the last element
      setParentPaths(newParentPaths); // Update the parentPaths stack
      setCurrentPath(lastParentPath); // Set the last parent path as the current path
    }
  };

  const handleConfirmSelection = () => {
    props.onFilesSelected(Array.from(selectedFiles));
  };

  const handleCancelSelection = () => {
    // Clear selection and close dropdown
    setSelectedFiles(new Set());
    props.onCancelSelection();
    // You might want to add a prop to control the visibility of this dropdown
    // and call a function here to close it.
  };

  return (
    <div className="file-browser-dropdown">
      <div className="file-browser-path">
        <VscArrowRight />
        <span className="current-path">{currentPath?.path || '/'}</span>
      </div>
      <ul className="file-browser-list">
        {files.map(file => (
          <li
            key={file.path}
            className={`file-browser-item ${file.type} ${
              selectedFiles.has(file.path) ? 'selected' : ''
            }`}
            onClick={() => handleFileClick(file)}
          >
            {file.type === 'directory' ? (
              <VscFolder className="file-icon" />
            ) : (
              <VscFile className="file-icon" />
            )}
            {file.name}
          </li>
        ))}
      </ul>
      {parentPaths.length > 0 && (
        <button onClick={handleBackClick}>
          <VscArrowLeft /> Back
        </button>
      )}
      <button onClick={handleConfirmSelection}>Confirm Selection</button>
      <button onClick={handleCancelSelection}>Cancel</button>
    </div>
  );
}
