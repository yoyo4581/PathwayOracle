from db import cQueryToServer, queryToServer
import random

class KG_InstanceFind:

    def __init__(self, user, email, subject=None):
            
        self.email = email
        if subject:
            self.subject = subject.replace(" ","_")
        self.user = user
        self.user_id = 0
        self.userFound = None
        # Check if a User exists, if it does then go ahead and output the number of instances and their respective subjects.
        self.checkCreateUser()


    def checkCreateUser(self):
        #Checking if the user name and email is found in the database, if not then create them and create an instance_id.
        checkQuery = """
        MATCH (u:User {username: $user, email: $email})
        RETURN u.id as userId
        """
        checkResults = cQueryToServer(query=checkQuery, parameters={'user': self.user, 'email':self.email})

        if checkResults:
            print("Found User")
            self.userFound = True
            self.user_id = checkResults[0]['userId']
            instances = self.showInstances()
            print(instances)
        else:
            print("Creating new User")
            self.userFound = False
            createQuery = """
            CREATE (u: User {id: apoc.create.uuid(), username: $user, email: $email})
            RETURN u.id as userID
            """
            retrieveId = cQueryToServer(query=createQuery, parameters={'user': self.user, 'email': self.email})
            self.user_id = retrieveId[0]['userID']

    #------------       Instance Manipulation             --------------------------------------------------

    def newInstance(self):
        # Generate a random number between 0 and 999
        random_number = random.randint(0, 999)
        self.instance_id = self.user + '_'+ str(random_number)
        
        findUser = """
        Match (u: User {id: $user_id})
        WITH u
        MERGE (i:Instance {instance_id: $instance_id, subject: $subject})
        MERGE (u)-[:CREATED {creation_date: datetime()}]->(i)
        RETURN i.instance_id as instanceId
        """
        createInstance = cQueryToServer(query=findUser, parameters={'user_id':self.user_id, 'instance_id':self.instance_id, 'subject':self.subject})
        self.instance_id = createInstance[0]['instanceId']
        self.graphName = 'myGraph_' + self.instance_id
        print(f"Use this instance_id to retrieve data after analysis. InstanceId: {self.instance_id}")
        
    def showInstances(self):
        findInstances = """
        MATCH (u: User {id: $user_id})-[:CREATED]->(i:Instance)
        WITH collect(i) as instances
        RETURN instances
        """
        retrievedInstances = cQueryToServer(query=findInstances, parameters={'user_id': self.user_id})
        return retrievedInstances

    def fromInstance(self, instance=None):
        if not instance:
            print('To use this method please insert an instance id, you can do this by using the showInstances method or creating a newInstance')
            return

        self.recoveryMode = True
        findInstances = """
        MATCH (u: User {id: $user_id})-[:CREATED]->(i:Instance {instance_id: $instance_id})
        RETURN i.instance_id as instanceId, i.subject as subject
        """
        retrieveData = cQueryToServer(query=findInstances, parameters={'user_id':self.user_id, 'instance_id':instance})
        if retrieveData:
            self.instance_id = retrieveData[0]['instanceId']
            self.subject = retrieveData[0]['subject']
            self.graphName = 'myGraph_' + self.instance_id


    def removeInstances(self, instanceList=[]):
        if not instanceList:
            print("Please specify a list of instance ids")
            instances = self.showInstances()
            print(instances)
            return  # Exit the method if no instances are provided
    
        for instance in instanceList:
            # Step 1: Return Nodes Before Deleting
            pre_delete_query = """
            MATCH (n:Instance {instance_id: $instance})
            RETURN n
            """
            nodes_before_deletion = cQueryToServer(query=pre_delete_query, parameters={'instance': instance})
            
            # Print nodes before deletion
            if nodes_before_deletion:
                print(f"Nodes to be deleted for instance {instance}: {nodes_before_deletion}")
            else:
                print(f"No nodes found for instance {instance}")
                continue
    
            # Step 2: Delete Nodes and Return Deleted Nodes
            delete_query = """
            MATCH (n:Instance {instance_id: $instance})
            DETACH DELETE n
            RETURN n
            """
            deleted_nodes = cQueryToServer(query=delete_query, parameters={'instance': instance})
            
            # Print confirmation of deletion
            if deleted_nodes:
                print(f"Deleted nodes for instance {instance}: {deleted_nodes}")
            else:
                print(f"No nodes were deleted for instance {instance}")
    
            # Step 3: Confirm Deletion
            confirm_query = """
            MATCH (n:Instance {instance_id: $instance})
            RETURN n
            """
            confirmation = cQueryToServer(query=confirm_query, parameters={'instance': instance})
            
            if not confirmation:
                print(f"Instance {instance} successfully deleted.")
            else:
                print(f"Instance {instance} still exists.")

            #Step 4: Delete marks from relationships
            query = """
            MATCH ()-[r]-()
            WHERE $instance_id IN r.instance_ids
            WITH r, [id IN r.instance_ids WHERE id <> $instance_id] AS updated_instance_ids
            SET r.instance_ids = updated_instance_ids
            RETURN COUNT(r) AS updatedCount
            """
            
            result = cQueryToServer(query=query, parameters={'instance_id': instance})
            updated_count = result[0]['updatedCount'] if result else 0
            print(f"Number of relationships with 'instance_ids' updated: {updated_count}")