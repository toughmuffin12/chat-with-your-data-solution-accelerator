param accountName string
param databaseName string
param containerName string
param maxThroughput int
param location string = resourceGroup().location
param tags object = {}

resource cosmosdbAccount 'Microsoft.DocumentDB/databaseAccounts@2021-04-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
  }
}

resource cosmosdbSqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2021-04-15' = {
  parent: cosmosdbAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {}
  }
}

resource cosmosdbSqlContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2021-04-15' = {
  parent: cosmosdbSqlDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/userId'
        ]
        kind: 'Hash'
      }
    }
    options: {
      throughput: maxThroughput
    }
  }
}

output accountName string = cosmosdbAccount.name
output databaseName string = cosmosdbSqlDatabase.name
output containerName string = cosmosdbSqlContainer.name
output endpoint string = cosmosdbAccount.properties.documentEndpoint
output identityPrincipalId string = cosmosdbAccount.identity.principalId
