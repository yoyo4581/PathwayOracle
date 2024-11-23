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
        """
        Perform pathway analysis using netGSA.R and ensure all necessary files exist before execution.
        """
        print("Entering pathwayAnalysis method")  # Debugging message
        try:
            # Get the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Construct the absolute path of netGSA.R
            netgsa_path = os.path.abspath(os.path.join(current_dir, 'netGSA.R'))
            print(f"Resolved netGSA script path: {netgsa_path}")
            
            # Resolve paths to input files
            self.pathGene = os.path.abspath('./PathwayOracle/testDataFiles/data_Matrix_Ductal_Age.txt')
            self.pathGroup = os.path.abspath('./PathwayOracle/testDataFiles/group_ductal_age_data.txt')
            self.write_to = os.path.abspath(self.write_to)
            print(f"Resolved pathGene: {self.pathGene}")
            print(f"Resolved pathGroup: {self.pathGroup}")
            print(f"Resolved write_to: {self.write_to}")

            # Check if required files exist
            self.check_file_exists(netgsa_path)
            self.check_file_exists(self.pathGene)
            self.check_file_exists(self.pathGroup)

            # Construct the command
            command = ["Rscript", netgsa_path, self.pathGene, self.pathGroup, current_dir, self.write_to]
            print(f"Running command: {command}")
            
            # Run the subprocess and capture output
            result = subprocess.run(command, capture_output=True, text=True)

            # Check if the command was successful
            if result.returncode == 0:
                print("Pathway analysis completed successfully.")
                print("Standard Output:")
                print(result.stdout)
            else:
                print(f"Error: Command failed with return code {result.returncode}")
                print("Standard Error:")
                print(result.stderr)

        except FileNotFoundError as e:
            print(f"File not found error: {e}")
        except subprocess.SubprocessError as e:
            print(f"Subprocess error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Exiting pathwayAnalysis method")  # Debugging message
