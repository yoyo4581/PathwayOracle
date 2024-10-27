import os
import subprocess

class PA_Analysis:

    gene_Data = {}
    path_Data = {}

    
    def __init__(self, pathGene=None, pathGroup=None, write_to = None):
        if pathGene:
            self.pathGene = pathGene
            self.check_file_exists(self.pathGene)

        if pathGroup:
            self.pathGroup = pathGroup
            self.check_file_exists(self.pathGroup)
        
        if write_to:
            self.write_to = os.path.abspath(write_to)
            self.check_file_exists(self.write_to)
            print(f"Output directory (absolute path): {self.write_to}")

    def check_file_exists(self, file_path):
        exists = os.path.exists(file_path)
        if exists:
            print(f"The file {file_path} exists.")
        else:
            print(f"The file {file_path} does not exist.")

    def pathwayAnalysis(self):
        print("Entering pathwayAnalysis method")  # Debugging message
        try:
            # Get the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Construct the absolute path of netGSA.R
            netgsa_path = os.path.join(current_dir, 'netGSA.R')
            print(f"The netGSA script path is: {netgsa_path}")
    
            # Conduct PA using netGSA and edges file
            command = ["Rscript", netgsa_path, self.pathGene, self.pathGroup, current_dir, self.write_to]
            print(f"Running command: {command}")
    
            # Run the subprocess and capture output
            result = subprocess.run(command, capture_output=True, text=True)
    
            # Check if the command was successful
            if result.returncode == 0:
                print("Pathway analysis completed successfully.")
            else:
                print(f"Error: Command failed with return code {result.returncode}")
            
            print("Standard Output:")
            print(result.stdout)
            print("Standard Error:")
            print(result.stderr)
    
        except Exception as e:
            print(f"An error occurred: {e}")
    
        finally:
            print("Exiting pathwayAnalysis method")  # Debugging message