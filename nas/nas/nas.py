import os
from io import BytesIO
from datetime import datetime
import hashlib
import json
from smb.SMBConnection import SMBConnection
from smb.smb_structs import OperationFailure

from dataclasses import dataclass, field

IMAGE_DATA_FILE = 'nas_images.json'

@dataclass
class Nas:
    """
    Class to manage Nas files
    """

    nas_username: str = field(default_factory=str)
    nas_password: str = field(default_factory=str)
    nas_ip: str = field(default_factory=str)

    conn = None

    image_data_filename: str = field(default_factory=str)
    image_data = []
    temp_image_data = []

    def __init__(self, nas_username: str, nas_ip: str, nas_password: str, image_data_filename: str=IMAGE_DATA_FILE):
        """
        Initialize the connection paramters
        """
        self.nas_username = nas_username
        self.nas_ip = nas_ip
        self.nas_password = nas_password
        
        self.image_data_filename = image_data_filename
        self.image_data = []
        self.temp_image_data = []

        self.conn = None

    def connect(self):
        try:
            self.conn = SMBConnection(self.nas_username, self.nas_password, 'local_machine', 'remote_machine', use_ntlm_v2=True)
            assert self.conn.connect(self.nas_ip, 139)
        except ValueError as e:
            print(e)

    def disconnect(self):
        try:
            self.conn.close()
        except ValueError as e:
            print(e)
        finally:
            self.conn = None

    def list_directory(self, shared_folder, path):
        try:
            files = self.conn.listPath(shared_folder, path)
            return [f.filename for f in files if f.filename not in ['.', '..']]
        except OperationFailure as e:
            print(f"Error listing directory {path}: {e}")
            return []

    def is_directory(self, shared_folder, path):
        try:
            file_info = self.conn.getAttributes(shared_folder, path)
            return file_info.isDirectory
        except OperationFailure:
            return False

    def join_path(self, *args):
        return '/'.join(arg.strip('/') for arg in args if arg)

    def normalize_path(self, path):
        return '/' + '/'.join(filter(None, path.split('/')))

    def get_parent_directory(self, path):
        normalized = self.normalize_path(path)
        parent = '/'.join(normalized.split('/')[:-1])
        return parent if parent else '/'

    def delete_file(self, shared_folder_name, file_path):
        try:
            self.conn.deleteFiles(shared_folder_name, file_path)
            print(f"Deleted {shared_folder_name}{file_path}")
        except ValueError as e:
            print(e)

    def delete_files_by_size(self, shared_folder_name, size_limit):
        """
        Assumes that the connection is already alive
        """

        impacted_files = [file_info for file_info in self.image_data if file_info['size'] <= size_limit]

        if impacted_files:
            print("The following files will be deleted based on the size limit:")
            for file_info in impacted_files:
                print(f"{file_info['path']} (Size: {file_info['size']} bytes)")

            confirm_delete = input("Do you want to proceed with deleting these files? (yes/no): ").strip().lower()
            if confirm_delete == 'yes':
                deleted_files = []
                for file_info in impacted_files:
                    self.delete_file(shared_folder_name, file_info['path'])
                    deleted_files.append(file_info)

            # Remove deleted files from image_data
            self.image_data = [file_info for file_info in self.image_data if file_info not in deleted_files]

            self.save_db()

            print(f"Removed {len(deleted_files)} entries from image_data")
        else:
            print("No files meet the size criteria for deletion.")

    def remove_duplicates_by_name(self, filename_appendice):
        self.connect()

        file_list = self.traverse_nas_folder('/Photos/PhotoLibrary')

        # Find and delete original files based on _upscaled files
        for file in file_list:
            if '_upscaled' in file:
                original_file = file.replace(filename_appendice, '')
                for f in file_list:
                    if f == original_file:
                        # Delete the original file
                        shared_folder_name = 'home'
                        self.delete_file(shared_folder_name, original_file)
                        break

        self.disconnect()

    def delete_duplicates(self, shared_folder_name, duplicate_group, date_choice):
        """
        Assumes that the connection is already alive
        """
        if date_choice == 'older':
            duplicate_group.sort(key=lambda x: datetime.fromtimestamp(x['creation_date']))
        elif date_choice == 'newer':
            duplicate_group.sort(key=lambda x: datetime.fromtimestamp(x['creation_date']), reverse=True)
        
        files_to_delete = duplicate_group[1:]  # All but the first file in the sorted group
        deleted_files = []

        for file_info in files_to_delete:
            try:
                self.delete_file(shared_folder_name, file_info['path'])
                deleted_files.append(file_info)
                print(f"Deleted duplicate: {file_info['path']}")
            except ValueError as e:
                print(f"Failed to delete {file_info['path']}: {str(e)}")
        
        # Remove deleted files from image_data
        self.image_data = [file_info for file_info in self.image_data if file_info not in deleted_files]

        self.save_db()

        print(f"Removed {len(deleted_files)} entries from image_data")

    def find_duplicates_in_db(self):
        hash_map = {}
        for file_info in self.image_data:
            file_hash = file_info['hash']
            if file_hash in hash_map:
                hash_map[file_hash].append(file_info)
            else:
                hash_map[file_hash] = [file_info]

        duplicates = [files for files in hash_map.values() if len(files) > 1]
        return duplicates

    def copy_files_to_nas_photos_library(self, local_folder, nas_share_name, nas_folder_path, nas_folder_name, delete_small_images, move_files=False):

        self.connect()

        # List folders in the Photos library
        print(f"\nFolders in {nas_folder_path}:")
        photos_folders = self.conn.listPath(nas_share_name, nas_folder_path)
        folder_names = []
        for folder in photos_folders:
            if folder.isDirectory and folder.filename not in ['.', '..']:
                print(f"- {folder.filename}")
                folder_names.append(folder.filename)

        # Check if the specified folder already exists, if not, create it
        if nas_folder_name not in folder_names:
            new_folder_path = f"{nas_folder_path}{nas_folder_name}"
            self.conn.createDirectory(nas_share_name, new_folder_path)
        else:
            new_folder_path = f"{nas_folder_path}{nas_folder_name}"

        # Retrieving the list of existing files
        existing_files = self.conn.listPath(nas_share_name, new_folder_path)

        # Copy or move files to the selected or new folder, skipping existing files
        try:
            for filename in os.listdir(local_folder):
                local_file_path = os.path.join(local_folder, filename)
                if os.path.isfile(local_file_path):
                    if delete_small_images and os.path.getsize(local_file_path) < 10000:
                        print(f"Deleting small image file: {filename}")
                        os.remove(local_file_path)
                        continue

                    remote_file_path = f"{new_folder_path}/{filename}"
                    try:
                        existing_filenames = [file.filename for file in existing_files]
                        if filename in existing_filenames:
                            print(f"File {filename} already exists in {nas_folder_name}. Skipping.")
                            continue
                    except ValueError as e:
                        print(e)
                        continue

                    with open(local_file_path, 'rb') as file_obj:
                        file_bytes = file_obj.read()
                        self.conn.storeFile(nas_share_name, remote_file_path, BytesIO(file_bytes))

                    if move_files:
                        os.remove(local_file_path)
                        print(f"Moved {filename} to {nas_folder_path}")
                    else:
                        print(f"Copied {filename} to {nas_folder_path}")
        except ValueError as e:
            print(f"{local_folder}: {e}")

        if move_files:
            # Remove the local folder after all files have been moved
            try:
                os.rmdir(local_folder)
                print(f"Deleted local folder: {local_folder}")
            except OSError as e:
                print(f"Error deleting folder {local_folder}: {e}")
        
        self.update_db(nas_share_name, nas_folder_path)

        self.disconnect()

    def traverse_nas_folder(self, nas_share_name, nas_folder_path, item_type='both', max_depth=None):
        """
        Traverse NAS folder and return list of files, folders, or both.

        Args:
            nas_share_name (str): Name of the NAS share.
            nas_folder_path (str): Path to the folder to traverse.
            item_type (str): Type of items to return ('files', 'folders', or 'both').
            max_depth (int, optional): Maximum depth to traverse. None for unlimited.

        Returns:
            list: List of file/folder paths.
        """
        items_list = []
        current_depth = nas_folder_path.count('/') if nas_folder_path != '/' else 0

        if max_depth is not None and current_depth > max_depth:
            return items_list

        try:
            nas_items = self.conn.listPath(nas_share_name, nas_folder_path)
            for item in nas_items:
                if item.filename not in ['.', '..']:
                    item_path = os.path.join(nas_folder_path, item.filename)
                    if item.isDirectory:
                        if item_type in ['folders', 'both']:
                            items_list.append(item_path)
                        items_list.extend(self.traverse_nas_folder(nas_share_name, item_path, item_type, max_depth))
                    elif item_type in ['files', 'both']:
                        items_list.append(item_path)
        except Exception as e:
            print(f"Error listing items in {nas_folder_path}: {e}")

        return items_list

    def calculate_file_hash(self, nas_share_name, nas_file_path, file):
        """
        Assumes that the connection is already alive
        """

        if file is None:
            file_obj = BytesIO()
            self.conn.retrieveFile(nas_share_name, nas_file_path, file_obj)
            file_obj.seek(0)
            file_hash = hashlib.md5(file_obj.read()).hexdigest()
            file_info = self.conn.getAttributes(nas_share_name, nas_file_path)
            return {
                'path': nas_file_path,
                'hash': file_hash,
                'creation_date': file_info.create_time,
                'size': file_info.file_size
            }
        else:
            file_obj = BytesIO()
            self.conn.retrieveFile(nas_share_name, nas_file_path, file_obj)
            file_obj.seek(0)
            file_hash = hashlib.md5(file_obj.read()).hexdigest()
            return {
                'path': nas_file_path,
                'hash': file_hash,
                'creation_date': file.create_time,
                'size': file.file_size
            }

    def load_db(self) -> bool:

        if not os.path.exists(self.image_data_filename):
            print(f"File does not exit {self.image_data_filename}")
            return False

        if self.image_data:
            self.image_data.clear()

        try:
            with open(file=self.image_data_filename, mode='r', encoding='utf-8') as f:
                self.image_data = json.load(f)
                print(f"Loaded: {self.image_data_filename}")

                return True
        except ValueError as e:
            print(e)
            return False

    def save_db(self):
        try:
            with open(file=self.image_data_filename, mode='w', encoding='utf-8') as f:
                json.dump(self.image_data, f, default=str)
        except ValueError as e:
            print(e)

    def update_db(self, nas_share_name, nas_folder_path):
        print(f"Updating {self.image_data_filename}...")
        self.temp_image_data.clear()
        self.recursive_hashes(nas_share_name, nas_folder_path)
        
        # Overwrite image_data with temp_image_data
        self.image_data = self.temp_image_data.copy()
        
        # Clear temp_image_data after copying
        self.temp_image_data.clear()
        
        self.save_db()
        
        print(f"Updated {self.image_data_filename} with {len(self.image_data)} entries")

    def recursive_hashes(self, nas_share_name, nas_folder_path):
        nas_files = self.conn.listPath(nas_share_name, nas_folder_path)
        for file in nas_files:
            if file.filename not in ['.', '..']:
                file_path = os.path.join(nas_folder_path, file.filename)
                if file.isDirectory:
                    self.recursive_hashes(nas_share_name, file_path)
                else:
                    # Check if the file path already exists in self.image_data
                    existing_file_info = next((item for item in self.image_data if item['path'] == file_path), None)
                    
                    if existing_file_info:
                        # If the file info already exists, copy it to temp_image_data
                        print(f"Skipping file {file_path}")
                        self.temp_image_data.append(existing_file_info)
                    else:
                        # If the file info doesn't exist, calculate the hash and add it
                        file_info = self.calculate_file_hash(nas_share_name, file_path, file)
                        print(f"Processing file {file_info['path']}; Hash {file_info['hash']}")
                        self.temp_image_data.append(file_info)

    def cleanup_nas_images(self, nas_share_name, nas_folder_path, update_db:bool=True, delete_duplicates:str='no', delete_files_smaller_than:int=0):
        """
        delete_duplicates: no, older or newer
        """

        self.connect()

        if self.load_db() or update_db:
            self.update_db(nas_share_name, nas_folder_path)

        # Ask the user if they want to delete files based on size
        if delete_files_smaller_than > 0:
            self.delete_files_by_size(nas_share_name, delete_files_smaller_than)

        if delete_duplicates in ['older','newer']:
            duplicates = self.find_duplicates_in_db()

            if duplicates:
                for dup_group in duplicates:
                        for idx, file_info in enumerate(dup_group):
                            print(f"{idx + 1}. {file_info['path']} (Created on {file_info['creation_date']}, Size: {file_info['size']} bytes)")

                for dup_group in duplicates:
                    self.delete_duplicates(nas_share_name, dup_group, delete_duplicates)

        self.disconnect()

    def list_small_files(self, image_data, size_limit):
        small_files = [file for file in image_data if file['size'] < size_limit]
        if small_files:
            print(f"Files smaller than {size_limit} bytes:")
            for file in small_files:
                print(f"{file['path']} (Size: {file['size']} bytes)")
            return small_files
        else:
            print(f"No files smaller than {size_limit} bytes found.")
            return []
