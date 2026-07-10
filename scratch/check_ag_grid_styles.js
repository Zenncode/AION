import fs from 'fs';
const path = 'node_modules/ag-grid-community/styles';
if (fs.existsSync(path)) {
  console.log('Files:', fs.readdirSync(path));
} else {
  console.log('Directory not found');
}
